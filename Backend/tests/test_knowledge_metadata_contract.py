from pathlib import Path

import pytest

from app.models.knowledge_entry import KnowledgeEntry
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_service import KnowledgeService
from app.services.sports_knowledge_policy import MetadataState, assess_metadata_field
from app.services.sports_knowledge_updater import SportsKnowledgeUpdater


HEADER_8 = "| ID | Topic | Role | Intent | Question | Answer | Source | Classification |"
HEADER_13 = (
    "| ID | Topic | Role | Intent | Sport | Entity | Question | Answer | Source_Name | "
    "Source_URL | Collected_At | Priority | Classification |"
)
HEADER_METADATA = HEADER_13[:-1] + (
    "| Source_Title | Source_Version | Verified_At | Effective_From | Effective_To | Rule_Set | "
    "Jurisdiction | Rights_Status | License | Rights_Evidence_URL | Rights_Checked_At | "
    "Approved_Uses | Authoring_Type | Record_Status |"
)


def _write_table(path: Path, header: str, row: str) -> None:
    path.write_text(f"{header}\n|---|---|---|---|---|---|---|---|\n{row}\n", encoding="utf-8")


def _legacy_13_row(entry_id: str, answer: str) -> str:
    return (
        f"| {entry_id} | Rules | CUSTOMER | SPORTS_KNOWLEDGE | tennis | Tennis | Question? | {answer} | "
        "Source | https://example.test/source | 2026-01-02 | 1 | static |"
    )


def _metadata_row(entry_id: str, answer: str, metadata: tuple[str, ...]) -> str:
    base = _legacy_13_row(entry_id, answer)[:-1].rstrip()
    return f"{base} | " + " | ".join(metadata) + " |"


def _new_entry(entry_id: str, **metadata: object) -> KnowledgeEntry:
    return KnowledgeEntry(
        id=entry_id,
        topic="Rules",
        role="CUSTOMER",
        intent="SPORTS_KNOWLEDGE",
        question="Question?",
        answer="Answer.",
        source="Source (https://example.test/source)",
        classification="static",
        sport="tennis",
        entity="Tennis",
        source_name="Source",
        source_url="https://example.test/source",
        collected_at="2026-01-02",
        **metadata,
    )


def _writer(knowledge_root: Path) -> SportsKnowledgeUpdater:
    updater = object.__new__(SportsKnowledgeUpdater)
    updater.repository = KnowledgeRepository(str(knowledge_root))
    return updater


def test_legacy_8_column_row_still_loads(tmp_path: Path) -> None:
    row = "| OLD-8 | Topic | CUSTOMER | FAQ | Question? | Answer. | Source | static |"
    _write_table(tmp_path / "old8.md", "|---|---|---|---|---|---|---|---|", row)

    entry = KnowledgeRepository(str(tmp_path)).get_entry_by_id("OLD-8")

    assert entry is not None
    assert entry.answer == "Answer."
    assert entry.rights_status is None
    assert entry.record_status is None


def test_legacy_13_column_row_still_loads(tmp_path: Path) -> None:
    _write_table(tmp_path / "old13.md", "|---|---|---|---|---|---|---|---|---|---|---|---|---|", _legacy_13_row("OLD-13", "Answer."))

    entry = KnowledgeRepository(str(tmp_path)).get_entry_by_id("OLD-13")

    assert entry is not None
    assert entry.sport == "tennis"
    assert entry.answer == "Answer."
    assert entry.collected_at == "2026-01-02"
    assert entry.verified_at is None
    assert entry.rights_status is None


def test_current_header_based_table_still_loads(tmp_path: Path) -> None:
    _write_table(tmp_path / "current.md", HEADER_13, _legacy_13_row("CURRENT", "Current answer."))

    entry = KnowledgeRepository(str(tmp_path)).get_entry_by_id("CURRENT")

    assert entry is not None
    assert entry.source_name == "Source"
    assert entry.source_url == "https://example.test/source"
    assert entry.answer == "Current answer."
    assert entry.rights_status is None


def test_new_metadata_columns_are_parsed_without_derivation(tmp_path: Path) -> None:
    row = _metadata_row(
        "WITH-METADATA",
        "Answer.",
        (
            "Exact Rules", "2025-edition", "2026-02-03", "2025-01-01", "2025-12-31", "USAP-2025", "US",
            " APPROVED ", "CC0-1.0", "https://example.test/rights", "2026-02-04", "local_storage, commercial_use",
            "original_summary", "active",
        ),
    )
    _write_table(tmp_path / "metadata.md", HEADER_METADATA, row)

    entry = KnowledgeRepository(str(tmp_path)).get_entry_by_id("WITH-METADATA")

    assert entry is not None
    assert entry.source_title == "Exact Rules"
    assert entry.source_version == "2025-edition"
    assert entry.verified_at == "2026-02-03"
    assert entry.effective_from == "2025-01-01"
    assert entry.effective_to == "2025-12-31"
    assert entry.rule_set == "USAP-2025"
    assert entry.jurisdiction == "US"
    assert entry.rights_status == "approved"
    assert entry.license == "CC0-1.0"
    assert entry.rights_evidence_url == "https://example.test/rights"
    assert entry.rights_checked_at == "2026-02-04"
    assert entry.approved_uses == ("local_storage", "commercial_use")
    assert entry.authoring_type == "original_summary"
    assert entry.record_status == "active"


def test_missing_metadata_remains_unknown(tmp_path: Path) -> None:
    _write_table(tmp_path / "missing.md", HEADER_13, _legacy_13_row("MISSING", "Answer."))

    entry = KnowledgeRepository(str(tmp_path)).get_entry_by_id("MISSING")

    assert entry is not None
    assert entry.collected_at == "2026-01-02"
    assert entry.verified_at is None
    assert entry.rights_checked_at is None
    assert entry.approved_uses is None
    assert entry.rights_status is None
    assert entry.record_status is None


def test_invalid_statuses_remain_distinguishable_from_missing_metadata(tmp_path: Path) -> None:
    row = _metadata_row(
        "INVALID",
        "Answer.",
        ("title", "v1", "", "", "", "", "", "approved_by_default", "", "", "", "", "original_summary", "unknown"),
    )
    _write_table(tmp_path / "invalid.md", HEADER_METADATA, row)

    entry = KnowledgeRepository(str(tmp_path)).get_entry_by_id("INVALID")

    assert entry is not None
    assert entry.rights_status == "approved_by_default"
    assert entry.record_status == "unknown"
    assert assess_metadata_field({"rights_status": entry.rights_status}, "rights_status").state == MetadataState.INVALID
    assert assess_metadata_field({"record_status": entry.record_status}, "record_status").state == MetadataState.INVALID
    assert entry.license is None
    assert entry.approved_uses is None


def test_all_declared_status_values_are_accepted(tmp_path: Path) -> None:
    rights_values = ("approved", "reference_only", "pending_review", "restricted")
    record_values = ("active", "draft", "conflicted", "superseded", "withdrawn")
    rows = []
    expected = {}
    status_pairs = [(status, "active") for status in rights_values]
    status_pairs.extend(("pending_review", status) for status in record_values)
    for index, (rights_status, record_status) in enumerate(status_pairs):
        entry_id = f"STATUS-{index}"
        rows.append(
            _metadata_row(
                entry_id,
                "Answer.",
                ("title", "v1", "", "", "", "", "", rights_status, "", "", "", "", "original_summary", record_status),
            )
        )
        expected[entry_id] = (rights_status, record_status)

    (tmp_path / "statuses.md").write_text(
        f"{HEADER_METADATA}\n|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    entries = KnowledgeRepository(str(tmp_path)).list_entries()

    assert {entry.id: (entry.rights_status, entry.record_status) for entry in entries} == expected


def test_approved_uses_are_normalized_as_a_tuple(tmp_path: Path) -> None:
    row = _metadata_row(
        "USES",
        "Answer.",
        ("title", "v1", "", "", "", "", "", "pending_review", "", "", "", "local_storage, commercial_use", "original_summary", "active"),
    )
    _write_table(tmp_path / "uses.md", HEADER_METADATA, row)

    entry = KnowledgeRepository(str(tmp_path)).get_entry_by_id("USES")

    assert entry is not None
    assert entry.rights_status == "pending_review"
    assert entry.approved_uses == ("local_storage", "commercial_use")


def test_malformed_approved_uses_empty_segments_are_preserved_for_policy_validation(tmp_path: Path) -> None:
    row = _metadata_row(
        "EMPTY-USE-SEGMENT",
        "Answer.",
        ("title", "v1", "", "", "", "", "", "approved", "", "", "", "retrieve_internal, ,display_answer", "original_summary", "active"),
    )
    _write_table(tmp_path / "empty-use-segment.md", HEADER_METADATA, row)

    entry = KnowledgeRepository(str(tmp_path)).get_entry_by_id("EMPTY-USE-SEGMENT")

    assert entry is not None
    assert entry.approved_uses == ("retrieve_internal", "", "display_answer")
    assessment = assess_metadata_field({"approved_uses": entry.approved_uses}, "approved_uses")
    assert assessment.state == MetadataState.INVALID


def test_duplicate_ids_keep_first_entry(tmp_path: Path) -> None:
    _write_table(tmp_path / "a.md", HEADER_8, "| DUP | Topic | CUSTOMER | FAQ | Q? | First | Source | static |")
    _write_table(tmp_path / "b.md", HEADER_8, "| DUP | Topic | CUSTOMER | FAQ | Q? | Second | Source | static |")

    entries = KnowledgeRepository(str(tmp_path)).list_entries()

    assert len(entries) == 1
    assert entries[0].answer == "First"


def test_unreviewed_static_entries_are_not_globally_filtered(tmp_path: Path) -> None:
    row = _metadata_row(
        "UNREVIEWED",
        "Answer.",
        ("title", "", "", "", "", "", "", "pending_review", "", "", "", "", "original_summary", "active"),
    )
    _write_table(tmp_path / "unreviewed.md", HEADER_METADATA, row)

    repository = KnowledgeRepository(str(tmp_path))

    assert [entry.id for entry in repository.get_static_entries()] == ["UNREVIEWED"]


def test_new_dataclass_fields_default_to_unknown() -> None:
    entry = KnowledgeEntry(
        id="MODEL",
        topic="topic",
        role="CUSTOMER",
        intent="FAQ",
        question="Q?",
        answer="A.",
        source="source",
        classification="static",
    )

    assert entry.source_title is None
    assert entry.source_version is None
    assert entry.rights_status is None
    assert entry.approved_uses is None
    assert entry.record_status is None


def test_writer_round_trips_metadata_through_extended_header(tmp_path: Path) -> None:
    entry = _new_entry(
        "ROUNDTRIP",
        source_title="Exact Rules",
        source_version="2025-edition",
        verified_at="2026-02-03",
        effective_from="2025-01-01",
        effective_to="2025-12-31",
        rule_set="USAP-2025",
        jurisdiction="US",
        rights_status="reference_only",
        license="Example-License",
        rights_evidence_url="https://example.test/rights",
        rights_checked_at="2026-02-04",
        approved_uses=("reference", "local_storage"),
        authoring_type="original_summary",
        record_status="active",
    )

    _writer(tmp_path)._persist_entry_to_markdown(entry)
    loaded = KnowledgeRepository(str(tmp_path)).get_entry_by_id(entry.id)

    assert loaded is not None
    for field in (
        "source_title", "source_version", "verified_at", "effective_from", "effective_to", "rule_set",
        "jurisdiction", "rights_status", "license", "rights_evidence_url", "rights_checked_at",
        "approved_uses", "authoring_type", "record_status",
    ):
        assert getattr(loaded, field) == getattr(entry, field)


def test_writer_keeps_none_metadata_blank(tmp_path: Path) -> None:
    entry = _new_entry("ROUNDTRIP-NONE")

    _writer(tmp_path)._persist_entry_to_markdown(entry)
    output_file = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    output = output_file.read_text(encoding="utf-8")
    loaded = KnowledgeRepository(str(tmp_path)).get_entry_by_id(entry.id)

    assert loaded is not None
    assert loaded.rights_status is None
    assert loaded.record_status is None
    assert loaded.verified_at is None
    assert loaded.approved_uses is None
    assert "| None |" not in output


def test_writer_round_trips_empty_approved_uses_tuple(tmp_path: Path) -> None:
    entry = _new_entry("ROUNDTRIP-EMPTY-USES", approved_uses=())

    _writer(tmp_path)._persist_entry_to_markdown(entry)
    loaded = KnowledgeRepository(str(tmp_path)).get_entry_by_id(entry.id)

    assert loaded is not None
    assert loaded.approved_uses == ()


def test_writer_preserves_existing_13_column_table_and_adds_extended_section(tmp_path: Path) -> None:
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    target.parent.mkdir(parents=True)
    original = (
        "# Existing knowledge\n\n"
        f"{HEADER_13}\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        f"{_legacy_13_row('OLD-ROW', 'Existing answer.')}\n"
    )
    target.write_text(original, encoding="utf-8")

    updater = _writer(tmp_path)
    updater._persist_entry_to_markdown(_new_entry("NEW-ROW", rights_status="pending_review"))
    updater._persist_entry_to_markdown(_new_entry("SECOND-NEW-ROW", rights_status="restricted"))
    output = target.read_text(encoding="utf-8")
    loaded_repository = KnowledgeRepository(str(tmp_path))

    assert output.startswith(original)
    assert output.count("| Source_Title | Source_Version |") == 1
    assert loaded_repository.get_entry_by_id("OLD-ROW") is not None
    assert loaded_repository.get_entry_by_id("NEW-ROW").rights_status == "pending_review"
    assert loaded_repository.get_entry_by_id("SECOND-NEW-ROW").rights_status == "restricted"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        *(("rights_status", value) for value in ("approved", "reference_only", "pending_review", "restricted")),
        *(("record_status", value) for value in ("active", "draft", "conflicted", "superseded", "withdrawn")),
    ],
)
def test_writer_accepts_declared_status_values(tmp_path: Path, field: str, value: str) -> None:
    entry = _new_entry(f"STATUS-{field}-{value}", **{field: f" {value.upper()} "})

    _writer(tmp_path)._persist_entry_to_markdown(entry)
    loaded = KnowledgeRepository(str(tmp_path)).get_entry_by_id(entry.id)

    assert loaded is not None
    assert getattr(loaded, field) == value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rights_status", "approved_by_default"),
        ("record_status", "current"),
        ("verified_at", "2026-02-30"),
        ("source_title", "Rules | extra column"),
        ("source_version", "first line\nsecond line"),
        ("approved_uses", ("local_storage", "")),
        ("approved_uses", ("commercial,use",)),
        ("approved_uses", ("[]",)),
    ],
)
def test_invalid_metadata_is_rejected_before_creating_file(tmp_path: Path, field: str, value: object) -> None:
    entry = _new_entry("INVALID-NEW")
    setattr(entry, field, value)
    output_file = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"

    with pytest.raises(ValueError):
        _writer(tmp_path)._persist_entry_to_markdown(entry)

    assert not output_file.exists()
    assert not output_file.parent.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_title", 123),
        ("authoring_type", ["original_summary"]),
        ("rights_status", 1),
        ("approved_uses", ["local_storage"]),
    ],
)
def test_metadata_with_wrong_type_is_rejected_before_creating_file(
    tmp_path: Path, field: str, value: object
) -> None:
    entry = _new_entry("INVALID-TYPE")
    setattr(entry, field, value)
    output_file = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"

    with pytest.raises(TypeError):
        _writer(tmp_path)._persist_entry_to_markdown(entry)

    assert not output_file.exists()
    assert not output_file.parent.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("collected_at", "2026-02-03"),
        ("verified_at", "2026-02-03"),
        ("effective_from", "2025-01-01"),
        ("effective_to", "2025-12-31"),
        ("rights_checked_at", "2026-02-04"),
    ],
)
def test_writer_accepts_iso_date_metadata(tmp_path: Path, field: str, value: str) -> None:
    entry = _new_entry("VALID-DATE")
    setattr(entry, field, value)

    _writer(tmp_path)._persist_entry_to_markdown(entry)
    loaded = KnowledgeRepository(str(tmp_path)).get_entry_by_id(entry.id)

    assert loaded is not None
    assert getattr(loaded, field) == value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("collected_at", "2026/02/03"),
        ("verified_at", "2026-2-3"),
        ("effective_from", "not-a-date"),
        ("effective_to", "2025-02-30"),
        ("rights_checked_at", "2026-02-04T10:00:00"),
    ],
)
def test_invalid_dates_are_rejected_before_creating_file(tmp_path: Path, field: str, value: str) -> None:
    entry = _new_entry("INVALID-DATE")
    setattr(entry, field, value)
    output_file = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        _writer(tmp_path)._persist_entry_to_markdown(entry)

    assert not output_file.exists()


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("rights_status", "unknown", ValueError),
        ("verified_at", "invalid-date", ValueError),
        ("source_title", 123, TypeError),
        ("approved_uses", ("bad,use",), ValueError),
        ("rights_evidence_url", "https://example.test/a\rb", ValueError),
    ],
)
def test_invalid_metadata_leaves_existing_file_unchanged(
    tmp_path: Path, field: str, value: object, error_type: type[Exception]
) -> None:
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    target.parent.mkdir(parents=True)
    original = "# Existing knowledge\n\n" + HEADER_13 + "\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    target.write_text(original, encoding="utf-8")
    entry = _new_entry("INVALID-EXISTING")
    setattr(entry, field, value)

    with pytest.raises(error_type):
        _writer(tmp_path)._persist_entry_to_markdown(entry)

    assert target.read_text(encoding="utf-8") == original


def test_authoring_type_remains_open_string_contract(tmp_path: Path) -> None:
    entry = _new_entry("AUTHORING-TYPE", authoring_type="project_defined_editorial_label")

    _writer(tmp_path)._persist_entry_to_markdown(entry)
    loaded = KnowledgeRepository(str(tmp_path)).get_entry_by_id(entry.id)

    assert loaded is not None
    assert loaded.authoring_type == "project_defined_editorial_label"


def test_writer_rejects_unescaped_markdown_delimiters_before_file_write(tmp_path: Path) -> None:
    entry = _new_entry("UNSAFE", source_title="Rules | extra column")
    output_file = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"

    with pytest.raises(ValueError, match="Markdown table delimiters"):
        _writer(tmp_path)._persist_entry_to_markdown(entry)

    assert not output_file.exists()


def test_metadata_only_update_propagates_to_repository_and_retriever(tmp_path: Path) -> None:
    initial = _new_entry(
        "METADATA-UPDATE",
        source_title="Original rules",
        source_version="v1",
        rights_status="pending_review",
        approved_uses=("reference",),
        record_status="draft",
    )
    _writer(tmp_path)._persist_entry_to_markdown(initial)

    repository = KnowledgeRepository(str(tmp_path))
    service = KnowledgeService(repository=repository)
    updated = _new_entry(
        "METADATA-UPDATE",
        source_version="v2",
        verified_at="2026-02-03",
        rights_status="reference_only",
        approved_uses=("local_storage",),
        record_status="active",
    )

    service.update_entry(updated)

    stored = repository.get_entry_by_id("METADATA-UPDATE")
    indexed = next(entry for entry in service.retriever._static_entries if entry.id == "METADATA-UPDATE")
    for entry in (stored, indexed):
        assert entry is not None
        assert entry.source_title == "Original rules"
        assert entry.source_version == "v2"
        assert entry.verified_at == "2026-02-03"
        assert entry.rights_status == "reference_only"
        assert entry.approved_uses == ("local_storage",)
        assert entry.record_status == "active"
