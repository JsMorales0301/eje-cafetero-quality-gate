from dashboard.labels import KIND_LABELS
from pipeline.corruption import KINDS


def test_every_corruption_kind_has_a_spanish_label():
    """A new kind added to the injector must not reach the dashboard without a Spanish name."""
    assert set(KIND_LABELS) == set(KINDS)


def test_labels_are_readable_phrases_and_unique():
    labels = list(KIND_LABELS.values())
    assert len(set(labels)) == len(labels)
    assert all(" " in label and label != key for key, label in KIND_LABELS.items())
