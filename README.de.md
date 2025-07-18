# Home Assistant Integration: Solar Prediction

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

Diese Integration für Home Assistant ruft Solarprognose-Daten vom Dienst [solarprognose.de](https://solarprognose.de) ab und stellt sie als Sensoren zur Verfügung.

## Voraussetzungen

* Eine laufende Home Assistant-Instanz.
* Ein Benutzerkonto bei [solarprognose.de](https://solarprognose.de), um einen persönlichen **Access-Token** zu erhalten.

## Installation

Diese Integration kann am einfachsten über den [Home Assistant Community Store (HACS)](https://hacs.xyz/) installiert werden.

1.  **(Bald verfügbar) Über die HACS-Standard-Liste:**
    * Navigieren Sie zu HACS > Integrationen und suchen Sie nach "Solar Prediction".
    * Klicken Sie auf "Installieren".

2.  **Manuelle Installation über ein "Custom Repository":**
    * Navigieren Sie zu HACS > Integrationen.
    * Klicken Sie auf das Drei-Punkte-Menü oben rechts und wählen Sie "Benutzerdefinierte Repositories".
    * Fügen Sie die URL dieses Repositories hinzu: `https://github.com/code-chicken/ha-solar-prediction`
    * Wählen Sie die Kategorie "Integration".
    * Klicken Sie auf "Hinzufügen".
    * Die Integration erscheint nun in der Suche und kann wie gewohnt installiert werden.

## Konfiguration

Nach der Installation über HACS müssen Sie die Integration in Home Assistant einrichten.

1.  Navigieren Sie zu **Einstellungen > Geräte & Dienste**.
2.  Klicken Sie unten rechts auf **+ Integration hinzufügen**.
3.  Suchen Sie nach **"Solar Prediction"** und wählen Sie die Integration aus.
4.  Geben Sie im Konfigurationsdialog Ihren **Access-Token** und Ihr **Projekt** (z.B. Ihre E-Mail-Adresse) ein.

## Erstellte Entitäten

Die Integration erstellt ein Gerät mit den folgenden Sensoren:

* **Today Total**: Die prognostizierte Gesamt-Solarenergie für den heutigen Tag in kWh.
* **Tomorrow Total**: Die prognostizierte Gesamt-Solarenergie für den morgigen Tag in kWh.
* **API Status**: Zeigt den Verbindungsstatus zur `solarprognose.de`-API an ("OK" oder eine Fehlermeldung).

Der "Today Total"-Sensor enthält zudem die detaillierte stündliche Prognose in seinen Attributen, die für Visualisierungen genutzt werden kann.

## Beispiel Lovelace-Karte

Hier ist ein Beispiel für eine [ApexCharts-Card](https://github.com/RomRider/apexcharts-card), um die stündliche Prognosekurve und den Tagesgesamtwert darzustellen:

```yaml
type: vertical-stack
cards:
  - type: entity
    entity: sensor.solar_prediction_today
    name: Solarprognose Heute (Gesamt)
  - type: custom:apexcharts-card
    graph_span: 24h
    span:
      start: day
    series:
      - entity: sensor.solar_prediction_today
        name: Leistungsprognose
        unit: kW
        type: area
        curve: smooth
        stroke_width: 2
        data_generator: |
          const forecast = entity.attributes.hourly_forecast;
          if (!forecast) return [];
          return Object.entries(forecast).map(([timestamp, values]) => {
            return [new Date(parseInt(timestamp) * 1000), values.power_kw];
          });
    yaxis:
      - min: 0
        decimals: 2
```
*Hinweis: Ersetzen Sie `sensor.solar_prediction_today` gegebenenfalls mit der korrekten Entity ID Ihres Sensors.*

## Beiträge

Fehlermeldungen und Feature-Wünsche sind willkommen! Bitte erstellen Sie dazu ein [Issue in diesem GitHub-Repository](https://github.com/code-chicken/ha-solar-prediction/issues).

## Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.