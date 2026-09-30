# Energy Day Balance

## Voraussetzungen

Die ausgewählten Entities sollten kumulative kWh-Zähler sein, zum Beispiel Sensoren mit `device_class: energy`, `state_class: total` oder `total_increasing` und `unit_of_measurement: kWh`.

## Berechnung

Für jeden ausgewählten Tag liest das Add-on die Home-Assistant-Historie von 00:00 bis 23:59:59 lokaler Zeit. Beim aktuellen Tag wird bis zum aktuellen Zeitpunkt gerechnet.

- `Solarertrag`: Summe der Tagesdifferenzen aller Solar-Entities
- `Netzbezug`: Tagesdifferenz der Bezugs-Entity
- `Netzeinspeisung`: Tagesdifferenz der Abgabe-Entity
- `Hausverbrauch`: `Solarertrag + Netzbezug - Netzeinspeisung`
- `Eigenverbrauch`: `Solarertrag - Netzeinspeisung`, begrenzt auf plausible Werte
- `Autarkiegrad`: `Eigenverbrauch / Hausverbrauch`
- `Selbstverbrauchsquote`: `Eigenverbrauch / Solarertrag`

Zähler-Resets werden berücksichtigt, indem positive Teilanstiege summiert werden.

## Einrichtung

1. Repository in Home Assistant als Add-on-Repository hinzufügen.
2. Add-on installieren und starten.
3. Add-on öffnen.
4. Solar-Entities, Netzbezug und Netzeinspeisung auswählen.
5. Speichern und Tages- bzw. Monatsübersicht ansehen.

## Hinweise

Wenn eine Entity keine ausreichende Historie für einen Tag hat, kann die Tagesdifferenz unvollständig sein. Prüfe in diesem Fall, ob der Sensor langfristige Statistik bzw. Historie liefert.
