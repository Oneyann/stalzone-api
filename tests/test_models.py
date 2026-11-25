import unittest

from stalzone_api.models import Emission, Lot, Page, Region


class RegionTest(unittest.TestCase):
    def test_accepts_any_case(self):
        self.assertIs(Region("eu"), Region.EU)

    def test_rejects_unknown_region(self):
        with self.assertRaises(ValueError):
            Region("xx")


class LotTest(unittest.TestCase):
    def test_price_uses_current_price_when_bid_exists(self):
        lot = Lot.from_dict({"itemId": "a", "amount": 2, "startPrice": 100, "buyoutPrice": 200, "currentPrice": 150})
        self.assertEqual(lot.price, 150)
        self.assertEqual(lot.total_price, 300)
        self.assertTrue(lot.has_bids)

    def test_price_falls_back_to_buyout_for_buyout_only_lot(self):
        lot = Lot.from_dict({"itemId": "a", "amount": 1, "startPrice": 0, "buyoutPrice": 200})
        self.assertEqual(lot.price, 200)
        self.assertFalse(lot.has_bids)


class EmissionTest(unittest.TestCase):
    def test_inactive_without_start(self):
        self.assertFalse(Emission.from_dict({}).active)

    def test_active_when_started_and_not_ended(self):
        emission = Emission.from_dict({"currentStart": "2026-01-01T10:00:00+00:00"})
        self.assertTrue(emission.active)


class PageTest(unittest.TestCase):
    def test_not_last_when_more_entries_exist(self):
        page = Page(items=[1, 2], total=5, offset=0)
        self.assertEqual(page.next_offset, 2)
        self.assertFalse(page.is_last)

    def test_last_page(self):
        page = Page(items=[1, 2], total=2, offset=0)
        self.assertTrue(page.is_last)


if __name__ == "__main__":
    unittest.main()
