# Home Assistant Energy Tools

Dieses Repository enthält ein Home-Assistant-Add-on:

- `homeassistant-energy-day`: Tages- und Monatsbilanz für Hausverbrauch, Solarertrag, Netzbezug, Netzeinspeisung, Autarkiegrad und Selbstverbrauchsquote.

## Nutzung

Das Repository kann als Home-Assistant-Add-on-Repository hinzugefügt werden. Danach das Add-on `Energy Day Balance` installieren, starten und über die Ingress-Oberfläche öffnen.

Die Konfiguration der kWh-Entities erfolgt direkt im Add-on:

- mehrere Solarquellen
- eine Entity für Netzbezug
- eine Entity für Netzeinspeisung

Die Berechnung nutzt die Home-Assistant-Historie der kumulativen kWh-Sensoren für volle Kalendertage oder den aktuellen Tag bis jetzt.
