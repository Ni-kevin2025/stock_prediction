from stock_prediction.account import Holding, TradingProfile, load_profile, merge_watchlist, save_profile


def test_profile_round_trip_is_local_json(tmp_path) -> None:
    profile = TradingProfile(
        available_cash=20_000, holdings=(Holding("600519", 100, 1300.0),), watchlist=("600519", "000858")
    )
    path = tmp_path / "profile.json"

    save_profile(path, profile)

    assert load_profile(path) == profile


def test_bulk_watchlist_import_merges_codes_without_duplicates() -> None:
    assert merge_watchlist(("600519",), "000858, 601318\n600519") == ("600519", "000858", "601318")
