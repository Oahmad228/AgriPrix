"""PREGEC notices: conservative publication date and country sentences."""

from src.research.pregec import country_sentences, publication_date


def test_publication_date_is_the_end_of_the_upload_month() -> None:
    url = "https://agrhymet.cilss.int/wp-content/uploads/2025/01/Avis_PREGEC_dec-2024_FR.pdf"
    assert publication_date(url, "2024-12") == "2025-01-31"
    assert publication_date("https://example.org/avis.pdf", "2024-02") == "2024-02-29"


def test_country_sentences_skip_prices_and_do_not_confuse_niger_with_nigeria() -> None:
    text = (
        "Des baisses de productions céréalières sont anticipées au Burkina Faso et au Nigeria. "
        "Les prix des céréales baissent au Mali grâce aux récoltes. "
        "La production céréalière du Niger est en hausse."
    )
    assert country_sentences(text) == [
        (
            "BFA",
            "Des baisses de productions céréalières sont anticipées au Burkina Faso et au Nigeria.",
        ),
        ("NER", "La production céréalière du Niger est en hausse."),
    ]
