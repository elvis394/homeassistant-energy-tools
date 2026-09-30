import unittest

from homeassistant_energy_day_path import add_app_path

add_app_path()

from app.energy import calculate_balance, calculate_entity_delta  # noqa: E402


def sample(state: str, timestamp: str) -> dict[str, str]:
    return {
        "entity_id": "sensor.energy",
        "state": state,
        "last_updated": timestamp,
    }


class EnergyCalculationTest(unittest.TestCase):
    def test_calculate_entity_delta_sums_positive_increments(self) -> None:
        delta = calculate_entity_delta(
            "sensor.energy",
            [
                sample("10.0", "2026-09-30T00:00:00+02:00"),
                sample("12.5", "2026-09-30T10:00:00+02:00"),
                sample("13.75", "2026-09-30T23:00:00+02:00"),
            ],
        )

        self.assertEqual(delta.delta_kwh, 3.75)
        self.assertEqual(delta.reset_count, 0)
        self.assertIsNone(delta.warning)

    def test_calculate_entity_delta_handles_meter_reset(self) -> None:
        delta = calculate_entity_delta(
            "sensor.energy",
            [
                sample("98", "2026-09-30T00:00:00+02:00"),
                sample("101", "2026-09-30T12:00:00+02:00"),
                sample("2", "2026-09-30T13:00:00+02:00"),
                sample("5", "2026-09-30T23:00:00+02:00"),
            ],
        )

        self.assertEqual(delta.delta_kwh, 8)
        self.assertEqual(delta.reset_count, 1)

    def test_calculate_balance_uses_standard_energy_formula(self) -> None:
        solar = calculate_entity_delta(
            "sensor.solar",
            [
                sample("100", "2026-09-30T00:00:00+02:00"),
                sample("118", "2026-09-30T23:00:00+02:00"),
            ],
        )
        grid_import = calculate_entity_delta(
            "sensor.import",
            [
                sample("50", "2026-09-30T00:00:00+02:00"),
                sample("57", "2026-09-30T23:00:00+02:00"),
            ],
        )
        grid_export = calculate_entity_delta(
            "sensor.export",
            [
                sample("20", "2026-09-30T00:00:00+02:00"),
                sample("26", "2026-09-30T23:00:00+02:00"),
            ],
        )

        balance = calculate_balance([solar], grid_import, grid_export)

        self.assertEqual(balance["solar_yield_kwh"], 18)
        self.assertEqual(balance["grid_import_kwh"], 7)
        self.assertEqual(balance["grid_export_kwh"], 6)
        self.assertEqual(balance["house_consumption_kwh"], 19)
        self.assertEqual(balance["self_consumed_kwh"], 12)
        self.assertEqual(balance["autarky_percent"], 63.2)
        self.assertEqual(balance["self_consumption_percent"], 66.7)


if __name__ == "__main__":
    unittest.main()
