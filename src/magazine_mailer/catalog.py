from magazine_mailer.models import MagazineSpec


MAGAZINES: dict[str, MagazineSpec] = {
    "economist": MagazineSpec(
        key="economist",
        display_name="The Economist",
        directory="01_economist",
        stale_after_days=10,
    ),
    "new_yorker": MagazineSpec(
        key="new_yorker",
        display_name="The New Yorker",
        directory="02_new_yorker",
    ),
    "atlantic": MagazineSpec(
        key="atlantic",
        display_name="The Atlantic",
        directory="04_atlantic",
    ),
    "wired": MagazineSpec(
        key="wired",
        display_name="Wired",
        directory="05_wired",
    ),
}
