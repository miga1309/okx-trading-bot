from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

try:
    import websocket  # websocket-client
except Exception:  # pragma: no cover
    websocket = None


class OkxWsManager:
    def __init__(self, cfg: Any, log_callback: Optional[Callable[[str], None]] = None):
        self.cfg = cfg
        self.log = log_callback or (lambda _msg: None)
        self.enabled = bool(getattr(cfg, 'ws_enabled', True))
        self.public_enabled = bool(getattr(cfg, 'ws_public_enabled', True))
        self.private_enabled = bool(getattr(cfg, 'ws_private_enabled', True))
        self.public_url = str(getattr(cfg, 'ws_public_url', '') or '').strip() or self._default_public_url()
        self.private_url = str(getattr(cfg, 'ws_private_url', '') or '').strip() or self._default_private_url()
        self.ping_interval_sec = max(10.0, float(getattr(cfg, 'ws_ping_interval_sec', 20.0) or 20.0))
        self.stale_after_sec = max(20.0, float(getattr(cfg, 'ws_stale_after_sec', 35.0) or 35.0))
        self.subscribe_chunk = max(1, int(getattr(cfg, 'ws_subscribe_chunk', 20) or 20))
        self._stop_evt = threading.Event()
        self._lock = threading.RLock()
        self._public_app = None
        self._private_app = None
        self._public_thread = None
        self._private_thread = None
        self._public_watchlist: List[str] = []
        self._public_connected = False
        self._private_connected = False
        self._private_logged_in = False
        self._public_last_msg_ts = 0.0
        self._private_last_msg_ts = 0.0
        self._public_last_ping_ts = 0.0
        self._private_last_ping_ts = 0.0
        self._public_error = ''
        self._private_error = ''
        self._positions: List[dict] = []
        self._account: Dict[str, Any] = {}
        self._orders: Dict[str, dict] = {}
        self._algo_orders: Dict[str, dict] = {}
        self._tickers: Dict[str, dict] = {}
        self._stats: Dict[str, int] = {'public_reconnects': 0, 'private_reconnects': 0, 'public_messages': 0, 'private_messages': 0}

    def _default_public_url(self) -> str:
        flag = str(getattr(self.cfg, 'flag', '1') or '1')
        return 'wss://wspap.okx.com:8443/ws/v5/public' if flag == '1' else 'wss://ws.okx.com:8443/ws/v5/public'

    def _default_private_url(self) -> str:
        flag = str(getattr(self.cfg, 'flag', '1') or '1')
        return 'wss://wspap.okx.com:8443/ws/v5/private' if flag == '1' else 'wss://ws.okx.com:8443/ws/v5/private'

    def start(self, inst_ids: Iterable[str]) -> None:
        if not self.enabled or websocket is None:
            if self.enabled and websocket is None:
                self.log('[WS] websocket-client не найден, WS отключён')
            return
        with self._lock:
            self._public_watchlist = [str(x).upper() for x in inst_ids if str(x).strip()]
        self._stop_evt.clear()
        if self.public_enabled and (self._public_thread is None or not self._public_thread.is_alive()):
            self._public_thread = threading.Thread(target=self._run_public_loop, name='okx-public-ws', daemon=True)
            self._public_thread.start()
        if self.private_enabled and (self._private_thread is None or not self._private_thread.is_alive()):
            self._private_thread = threading.Thread(target=self._run_private_loop, name='okx-private-ws', daemon=True)
            self._private_thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        for app in (self._public_app, self._private_app):
            try:
                if app is not None:
                    app.close()
            except Exception:
                pass
        for th in (self._public_thread, self._private_thread):
            try:
                if th is not None and th.is_alive():
                    th.join(timeout=2.0)
            except Exception:
                pass
        self._public_connected = False
        self._private_connected = False
        self._private_logged_in = False

    def health_snapshot(self) -> dict:
        now = time.time()
        pub_ok = self.public_enabled and self._public_connected and (now - float(self._public_last_msg_ts or 0.0)) <= self.stale_after_sec
        priv_ok = self.private_enabled and self._private_connected and self._private_logged_in and (now - float(self._private_last_msg_ts or 0.0)) <= self.stale_after_sec
        return {
            'public': {
                'ok': bool(pub_ok),
                'connected': bool(self._public_connected),
                'last_msg_age_sec': round(max(0.0, now - float(self._public_last_msg_ts or 0.0)), 3) if self._public_last_msg_ts else 1e12,
                'error': self._public_error,
                'reconnects': int(self._stats.get('public_reconnects', 0)),
                'messages': int(self._stats.get('public_messages', 0)),
            },
            'private': {
                'ok': bool(priv_ok),
                'connected': bool(self._private_connected),
                'logged_in': bool(self._private_logged_in),
                'last_msg_age_sec': round(max(0.0, now - float(self._private_last_msg_ts or 0.0)), 3) if self._private_last_msg_ts else 1e12,
                'error': self._private_error,
                'reconnects': int(self._stats.get('private_reconnects', 0)),
                'messages': int(self._stats.get('private_messages', 0)),
            },
        }

    def public_ready(self) -> bool:
        return bool(self.health_snapshot().get('public', {}).get('ok', False))

    def private_ready(self) -> bool:
        return bool(self.health_snapshot().get('private', {}).get('ok', False))

    def get_positions_snapshot(self, max_age_sec: float = 10.0) -> Optional[List[dict]]:
        if not self.private_ready():
            return None
        if (time.time() - float(self._private_last_msg_ts or 0.0)) > max_age_sec:
            return None
        with self._lock:
            return [dict(item) for item in self._positions]

    def get_account_snapshot(self, max_age_sec: float = 10.0) -> Optional[dict]:
        if not self.private_ready():
            return None
        if (time.time() - float(self._private_last_msg_ts or 0.0)) > max_age_sec:
            return None
        with self._lock:
            return dict(self._account or {})

    def get_ticker_snapshot(self, inst_id: str, max_age_sec: float = 8.0) -> Optional[dict]:
        if not self.public_ready():
            return None
        item = dict((self._tickers or {}).get(str(inst_id).upper(), {}) or {})
        ts = float(item.get('_recv_ts') or 0.0)
        if not item or (time.time() - ts) > max_age_sec:
            return None
        item.pop('_recv_ts', None)
        return item

    def get_algo_order_snapshot(self, algo_id: str) -> Optional[dict]:
        algo_id = str(algo_id or '').strip()
        if not algo_id:
            return None
        with self._lock:
            row = dict((self._algo_orders or {}).get(algo_id, {}) or {})
        return row or None

    def get_pending_algo_orders(self, inst_id: str) -> List[dict]:
        inst_id = str(inst_id or '').upper()
        with self._lock:
            rows = [dict(v) for v in (self._algo_orders or {}).values() if str(v.get('instId') or '').upper() == inst_id]
        return rows

    def _ws_login_args(self) -> dict:
        ts = str(time.time())
        prehash = f'{ts}GET/users/self/verify'
        sign = base64.b64encode(hmac.new(str(getattr(self.cfg, 'secret_key', '')).encode(), prehash.encode(), hashlib.sha256).digest()).decode()
        return {'op': 'login', 'args': [{'apiKey': str(getattr(self.cfg, 'api_key', '')), 'passphrase': str(getattr(self.cfg, 'passphrase', '')), 'timestamp': ts, 'sign': sign}]}

    def _run_public_loop(self) -> None:
        while not self._stop_evt.is_set() and self.enabled and self.public_enabled:
            try:
                self._stats['public_reconnects'] = int(self._stats.get('public_reconnects', 0)) + 1
                app = websocket.WebSocketApp(self.public_url, on_open=self._on_public_open, on_message=self._on_public_message, on_error=self._on_public_error, on_close=self._on_public_close)
                self._public_app = app
                app.run_forever(ping_interval=int(self.ping_interval_sec), ping_timeout=max(5, int(self.ping_interval_sec // 2)))
            except Exception as exc:
                self._public_error = str(exc)
                logging.exception('Public WS loop failed')
            if not self._stop_evt.is_set():
                time.sleep(3.0)

    def _run_private_loop(self) -> None:
        while not self._stop_evt.is_set() and self.enabled and self.private_enabled:
            try:
                self._stats['private_reconnects'] = int(self._stats.get('private_reconnects', 0)) + 1
                app = websocket.WebSocketApp(self.private_url, on_open=self._on_private_open, on_message=self._on_private_message, on_error=self._on_private_error, on_close=self._on_private_close)
                self._private_app = app
                app.run_forever(ping_interval=int(self.ping_interval_sec), ping_timeout=max(5, int(self.ping_interval_sec // 2)))
            except Exception as exc:
                self._private_error = str(exc)
                logging.exception('Private WS loop failed')
            if not self._stop_evt.is_set():
                time.sleep(3.0)

    def _send_chunks(self, app: Any, op: str, args: List[dict]) -> None:
        if app is None or not args:
            return
        for i in range(0, len(args), self.subscribe_chunk):
            payload = {'op': op, 'args': args[i:i+self.subscribe_chunk]}
            try:
                app.send(json.dumps(payload, ensure_ascii=False))
            except Exception:
                logging.exception('WS send failed: %s', payload)

    def _on_public_open(self, app) -> None:
        self._public_connected = True
        self._public_error = ''
        self._public_last_msg_ts = time.time()
        watchlist = list(self._public_watchlist)
        ticker_args = [{'channel': 'tickers', 'instId': inst_id} for inst_id in watchlist]
        self._send_chunks(app, 'subscribe', ticker_args)
        self.log(f'[WS] public connected, subscribed tickers={len(watchlist)}')

    def _on_private_open(self, app) -> None:
        self._private_connected = True
        self._private_logged_in = False
        self._private_error = ''
        self._private_last_msg_ts = time.time()
        try:
            app.send(json.dumps(self._ws_login_args(), ensure_ascii=False))
        except Exception:
            logging.exception('Private WS login send failed')

    def _on_public_message(self, _app, message: str) -> None:
        self._public_last_msg_ts = time.time()
        self._stats['public_messages'] = int(self._stats.get('public_messages', 0)) + 1
        self._handle_message(message, private=False)

    def _on_private_message(self, app, message: str) -> None:
        self._private_last_msg_ts = time.time()
        self._stats['private_messages'] = int(self._stats.get('private_messages', 0)) + 1
        try:
            payload = json.loads(message)
        except Exception:
            return
        event = str(payload.get('event') or '').lower()
        if event == 'login':
            code = str(payload.get('code') or '0')
            self._private_logged_in = code == '0'
            if self._private_logged_in:
                args = [
                    {'channel': 'positions', 'instType': 'SWAP'},
                    {'channel': 'orders', 'instType': 'SWAP'},
                    {'channel': 'account'},
                    {'channel': 'algo-orders', 'instType': 'SWAP'},
                ]
                self._send_chunks(app, 'subscribe', args)
                self.log('[WS] private login ok, subscribed positions/orders/account/algo-orders')
            else:
                self._private_error = str(payload.get('msg') or 'private_login_failed')
            return
        self._handle_payload(payload, private=True)

    def _handle_message(self, message: str, private: bool) -> None:
        try:
            payload = json.loads(message)
        except Exception:
            return
        self._handle_payload(payload, private=private)

    def _handle_payload(self, payload: dict, private: bool) -> None:
        arg = dict(payload.get('arg') or {})
        channel = str(arg.get('channel') or '').lower()
        data = list(payload.get('data', []) or [])
        if not channel:
            return
        with self._lock:
            if channel == 'tickers':
                for row in data:
                    item = dict(row or {})
                    inst_id = str(item.get('instId') or '').upper()
                    if inst_id:
                        item['_recv_ts'] = time.time()
                        self._tickers[inst_id] = item
            elif channel == 'positions':
                self._positions = [dict(row or {}) for row in data]
            elif channel in {'account', 'balance_and_position', 'balance and positions'}:
                if data:
                    self._account = dict(data[0] or {})
            elif channel == 'orders':
                for row in data:
                    item = dict(row or {})
                    ord_id = str(item.get('ordId') or item.get('clOrdId') or '').strip()
                    if ord_id:
                        self._orders[ord_id] = item
            elif channel in {'algo-orders', 'algo orders', 'advance-algo-orders'}:
                for row in data:
                    item = dict(row or {})
                    algo_id = str(item.get('algoId') or item.get('algoClOrdId') or '').strip()
                    if algo_id:
                        self._algo_orders[algo_id] = item

    def _on_public_error(self, _app, error) -> None:
        self._public_error = str(error)
        logging.warning('Public WS error: %s', error)

    def _on_private_error(self, _app, error) -> None:
        self._private_error = str(error)
        logging.warning('Private WS error: %s', error)

    def _on_public_close(self, _app, _code, _msg) -> None:
        self._public_connected = False

    def _on_private_close(self, _app, _code, _msg) -> None:
        self._private_connected = False
        self._private_logged_in = False
