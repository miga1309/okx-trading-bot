[v093_2]
- Стопы пересчитываются только по закрытию свечи: ATR для 1-2 юнитов, Turtle exit для 3-4 юнитов.
- Убран рабочий сценарий cancel + place для обновления стопов; изменение стопа теперь идёт через amend.
- Добавлена проверка первичного стопа через 5 секунд после открытия позиции с аварийным закрытием, если стоп не подтверждён на бирже.
- Добавлен минутный health-check стопов с восстановлением пропавшего стопа и паузой между stop-ордерами.
- Обновлены логи stop engine для стратегии, initial stop и health-check.

[v091]
- Added Good Positions review tab in Market Scanner
- Scanner popups use candle-only charts
- Verdict dropdown colored in closed and expanded states
- RIPPING recalibrated to candle gap logic
- SAW recalibrated to range re-entry / repeated zone logic

# v090

- Калибровка DEAD/RIPPING по результатам ручной валидации.
- Русские вкладки сканнера рынка.
- Verdict окрашивается в таблице и popup.
- Popup scanner очищен: только свечи, без линий Дончьяна и лишних аннотаций.
- Risk Radar скрыт из GUI.
- Чистый релиз с одним main_v090.py.
