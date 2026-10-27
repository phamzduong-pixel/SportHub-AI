from pathlib import Path
from unittest.mock import MagicMock, patch

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.sports_knowledge_updater import (
    ExtractedSportsFact,
    KnowledgeUpdateAction,
    SportsKnowledgeUpdater,
)
from app.services.sports_knowledge_policy import KnowledgeUseDecision, PolicyOutcome
from app.services.sports_knowledge_review_ledger import ReviewLedgerResult


class _SyntheticStoreLocalTestGate:
    """Non-persistent test double; it does not create or sign ledger decisions."""
    status = "valid"

    @staticmethod
    def authorizes(entry, purpose):
        identifier = getattr(entry, "id", "")
        return purpose == "store_local" and (
            identifier.startswith("AUTO-") or identifier in {"OLD", "AUTO-OLD", "AUTO-OTHER"}
        )


def _fact(**changes):
    values = dict(
        sport="tennis", entity="Example Player", topic="rules",
        question="What are the rules for Example Player?",
        answer="An example answer for the knowledge record.",
        source_name="ITF", source_url="https://www.itftennis.com/example",
        collected_at="2026-01-01",
    )
    values.update(changes)
    return ExtractedSportsFact(**values)


def _updater(tmp_path: Path, knowledge_retriever=None, monkeypatch=None):
    updater = SportsKnowledgeUpdater(
        repository=KnowledgeRepository(str(tmp_path)),
        knowledge_retriever=knowledge_retriever,
        review_ledger=_SyntheticStoreLocalTestGate(),
    )
    if monkeypatch is not None:
        # These cases exercise Markdown writer/upsert mechanics only. The real
        # policy decision remains covered by the fail-closed tests below.
        monkeypatch.setattr(
            "app.services.sports_knowledge_updater.evaluate_reviewed_knowledge_use",
            lambda entry, purpose, ledger: KnowledgeUseDecision(
                PolicyOutcome.ALLOWED,
                "synthetic writer-mechanics test seam",
            ),
        )
    return updater


def _reload(tmp_path: Path, entry_id: str):
    return KnowledgeRepository(str(tmp_path)).get_entry_by_id(entry_id)


def test_duplicate_content_metadata_update_is_durable(tmp_path, monkeypatch):
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(), persist_markdown=True)
    assert inserted.action == KnowledgeUpdateAction.INSERTED
    entry_id = inserted.entry_id

    result = updater.apply_fact_update(
        _fact(source_title="Rules edition", collected_at="2026-01-02"),
        persist_markdown=True,
    )
    assert result.action == KnowledgeUpdateAction.UPDATED
    loaded = _reload(tmp_path, entry_id)
    assert loaded.source_title == "Rules edition"
    assert loaded.rights_status is None
    assert loaded.approved_uses is None
    assert loaded.record_status is None
    assert loaded.collected_at == "2026-01-02"
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    assert target.read_text(encoding="utf-8").count(f"| {entry_id} |") == 1


def test_collected_at_only_update_is_reported_and_persisted(tmp_path, monkeypatch):
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(), persist_markdown=True)

    result = updater.apply_fact_update(
        _fact(collected_at="2026-01-02"), persist_markdown=True,
    )

    assert result.action == KnowledgeUpdateAction.UPDATED
    assert "Metadata updated" in result.message
    assert _reload(tmp_path, inserted.entry_id).collected_at == "2026-01-02"
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    assert target.read_text(encoding="utf-8").count(f"| {inserted.entry_id} |") == 1


def test_identical_content_and_metadata_is_a_noop(tmp_path, monkeypatch):
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(), persist_markdown=True)
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    original = target.read_bytes()

    result = updater.apply_fact_update(_fact(), persist_markdown=True)

    assert result.action == KnowledgeUpdateAction.DUPLICATE_SKIPPED
    assert target.read_bytes() == original
    assert target.read_text(encoding="utf-8").count(f"| {inserted.entry_id} |") == 1


def test_unspecified_and_blank_metadata_do_not_overwrite_existing(tmp_path, monkeypatch):
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(source_title="Existing title"), persist_markdown=True)
    result = updater.apply_fact_update(
        _fact(source_title=" ", rights_status=" ", approved_uses=None,
              record_status=None, source_version="v2"), persist_markdown=True,
    )
    assert result.action == KnowledgeUpdateAction.UPDATED
    loaded = _reload(tmp_path, inserted.entry_id)
    assert loaded.source_title == "Existing title"
    assert loaded.source_version == "v2"
    assert loaded.rights_status is None
    assert loaded.record_status is None
    assert loaded.approved_uses is None


def test_changed_content_retains_supplied_metadata_and_persists(tmp_path, monkeypatch):
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(), persist_markdown=True)
    result = updater.apply_fact_update(
        _fact(answer="A revised example answer for this record.", source_version="v2",
              collected_at="2026-01-03"), persist_markdown=True,
    )
    assert result.action == KnowledgeUpdateAction.UPDATED
    loaded = _reload(tmp_path, inserted.entry_id)
    assert loaded.answer == "A revised example answer for this record."
    assert loaded.source_version == "v2"
    assert loaded.rights_status is None


def test_changed_content_cannot_inherit_prior_approval(tmp_path, monkeypatch):
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(), persist_markdown=True)
    entry = updater.repository.get_entry_by_id(inserted.entry_id)
    # Synthetic in-memory reviewed state: the ordinary updater must not replace
    # a reviewed claim or apply its decision to new content.
    entry.rights_status = "approved"
    entry.record_status = "active"
    entry.approved_uses = ("retrieve_internal", "display_answer")
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    original = target.read_bytes()
    result = updater.apply_fact_update(
        _fact(answer="A different claim from a later source.", collected_at="2026-01-03",
              rights_status=None, record_status=None, approved_uses=None),
        persist_markdown=True,
    )
    assert result.action == KnowledgeUpdateAction.REJECTED
    assert target.read_bytes() == original
    assert _reload(tmp_path, inserted.entry_id).answer == "An example answer for the knowledge record."


def test_approved_status_is_normalized_before_claim_change_guard(tmp_path, monkeypatch):
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(), persist_markdown=True)
    entry = updater.repository.get_entry_by_id(inserted.entry_id)
    entry.rights_status = " APPROVED "
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    original = target.read_bytes()

    result = updater.apply_fact_update(
        _fact(answer="A different claim from a later source.", collected_at="2026-01-03",
              rights_status=None, record_status=None, approved_uses=None),
        persist_markdown=True,
    )

    assert result.action == KnowledgeUpdateAction.REJECTED
    assert entry.answer == "An example answer for the knowledge record."
    assert target.read_bytes() == original


def test_invalid_metadata_or_write_failure_does_not_change_file_or_index(tmp_path, monkeypatch):
    mock_index = MagicMock()
    updater = _updater(tmp_path, knowledge_retriever=mock_index, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(), persist_markdown=True)
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    original = target.read_bytes()
    entry = updater.repository.get_entry_by_id(inserted.entry_id)

    bad = updater.apply_fact_update(_fact(rights_status="approved_by_default"), persist_markdown=True)
    assert bad.action == KnowledgeUpdateAction.REJECTED
    assert target.read_bytes() == original
    assert entry.rights_status is None

    invalid_date = updater.apply_fact_update(
        _fact(collected_at="2025-not-a-date"), persist_markdown=True,
    )
    assert invalid_date.action == KnowledgeUpdateAction.REJECTED
    assert target.read_bytes() == original
    assert entry.collected_at == "2026-01-01"

    with patch("app.services.sports_knowledge_updater.os.replace", side_effect=OSError("simulated failure")):
        failed = updater.apply_fact_update(
            _fact(source_version="v2", collected_at="2026-01-04"), persist_markdown=True,
        )
    assert failed.action == KnowledgeUpdateAction.REJECTED
    assert target.read_bytes() == original
    assert entry.source_version is None
    assert not list(target.parent.glob(".knowledge-*.tmp"))
    mock_index.update_entry.assert_not_called()


def test_ordinary_updater_cannot_self_grant_permissions_or_activate_record(tmp_path, monkeypatch):
    mock_index = MagicMock()
    updater = _updater(tmp_path, knowledge_retriever=mock_index, monkeypatch=monkeypatch)

    result = updater.apply_fact_update(
        _fact(
            rights_status="approved",
            approved_uses=("retrieve_internal", "prompt_llm_external"),
            record_status="active",
            license="claimed-license",
            rights_evidence_url="https://example.test/license",
            rights_checked_at="2026-01-01",
            verified_at="2026-01-01",
        ),
        persist_markdown=True,
    )

    assert result.action == KnowledgeUpdateAction.REJECTED
    assert "reviewer-controlled metadata" in result.message
    assert updater.repository.list_entries() == []
    assert not (tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md").exists()
    mock_index.index_entry.assert_not_called()


def test_persistent_storage_fails_closed_without_authenticated_store_local_review(tmp_path):
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    target.parent.mkdir(parents=True)
    target.write_text("# Existing fixture file\n", encoding="utf-8")
    original = target.read_bytes()
    updater = SportsKnowledgeUpdater(
        repository=KnowledgeRepository(str(tmp_path)),
        review_ledger=ReviewLedgerResult("missing", {}),
    )

    result = updater.apply_fact_update(_fact(), persist_markdown=True)

    assert result.action == KnowledgeUpdateAction.REJECTED
    assert "store_local review decision" in result.message
    assert target.read_bytes() == original
    assert updater.repository.list_entries() == []


def test_ledger_allow_alone_cannot_store_record_with_missing_rights_metadata(tmp_path):
    updater = SportsKnowledgeUpdater(
        repository=KnowledgeRepository(str(tmp_path)),
        review_ledger=_SyntheticStoreLocalTestGate(),
    )

    result = updater.apply_fact_update(_fact(), persist_markdown=True)

    assert result.action == KnowledgeUpdateAction.REJECTED
    assert "approved metadata" in result.message
    assert updater.repository.list_entries() == []
    assert not (tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md").exists()


def test_unreviewed_fact_is_not_added_to_in_memory_repository_or_index(tmp_path):
    mock_index = MagicMock()
    updater = SportsKnowledgeUpdater(
        repository=KnowledgeRepository(str(tmp_path)),
        knowledge_retriever=mock_index,
        review_ledger=ReviewLedgerResult("missing", {}),
    )

    result = updater.apply_fact_update(_fact(), persist_markdown=False)

    assert result.action == KnowledgeUpdateAction.REJECTED
    assert updater.repository.list_entries() == []
    mock_index.index_entry.assert_not_called()


def test_changed_claim_clears_prior_review_metadata_before_persistence(tmp_path, monkeypatch):
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(), persist_markdown=True)
    entry = updater.repository.get_entry_by_id(inserted.entry_id)
    entry.rights_status = "pending_review"
    entry.record_status = "draft"
    entry.approved_uses = ()
    entry.verified_at = "2026-01-01"
    entry.rights_checked_at = "2026-01-01"

    result = updater.apply_fact_update(
        _fact(answer="A revised example answer for this record.", collected_at="2026-01-02"),
        persist_markdown=True,
    )

    assert result.action == KnowledgeUpdateAction.UPDATED
    reloaded = _reload(tmp_path, inserted.entry_id)
    assert reloaded.answer == "A revised example answer for this record."
    assert reloaded.rights_status is None
    assert reloaded.record_status is None
    assert reloaded.approved_uses is None
    assert reloaded.verified_at is None
    assert reloaded.rights_checked_at is None


def test_failed_first_write_does_not_add_to_repository_or_index(tmp_path):
    mock_index = MagicMock()
    updater = _updater(tmp_path, knowledge_retriever=mock_index)

    with patch("app.services.sports_knowledge_updater.os.replace", side_effect=OSError("simulated failure")):
        result = updater.apply_fact_update(_fact(), persist_markdown=True)

    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    assert result.action == KnowledgeUpdateAction.REJECTED
    assert not target.exists()
    assert updater.repository.list_entries() == []
    mock_index.index_entry.assert_not_called()
    assert not list(target.parent.glob(".knowledge-*.tmp"))


def test_legacy_auto_row_can_be_updated_without_losing_other_rows(tmp_path, monkeypatch):
    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    target.parent.mkdir(parents=True)
    header = "| ID | Topic | Role | Intent | Sport | Entity | Question | Answer | Source_Name | Source_URL | Collected_At | Priority | Classification |\n"
    separator = "|" + "---|" * 13 + "\n"
    def row(entry_id, answer):
        return f"| {entry_id} | rules | CUSTOMER | SPORTS_KNOWLEDGE | tennis | Example Player | What are the rules for Example Player? | {answer} | ITF | https://www.itftennis.com/example | 2026-01-01 | 2 | static |\n"
    target.write_text(header + separator + row("AUTO-OLD", "An example answer for the knowledge record.") + row("AUTO-OTHER", "Other answer."), encoding="utf-8")
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    result = updater.apply_fact_update(_fact(source_title="New metadata"), persist_markdown=True)
    assert result.action == KnowledgeUpdateAction.UPDATED
    assert _reload(tmp_path, "AUTO-OLD").source_title == "New metadata"
    assert _reload(tmp_path, "AUTO-OTHER").answer == "Other answer."
    assert target.read_text(encoding="utf-8").count("| AUTO-OLD |") == 1


def test_update_from_other_markdown_file_is_rejected_without_shadow_copy(tmp_path, monkeypatch):
    source = tmp_path / "sports" / "tennis.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "| ID | Topic | Role | Intent | Sport | Entity | Question | Answer | Source_Name | Source_URL | Collected_At | Priority | Classification |\n"
        "|" + "---|" * 13 + "\n"
        "| OLD | rules | CUSTOMER | SPORTS_KNOWLEDGE | tennis | Example Player | What are the rules for Example Player? | An example answer for the knowledge record. | ITF | https://www.itftennis.com/example | 2026-01-01 | 2 | static |\n",
        encoding="utf-8",
    )
    original = source.read_bytes()
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    result = updater.apply_fact_update(_fact(source_version="v2"), persist_markdown=True)
    assert result.action == KnowledgeUpdateAction.REJECTED
    assert source.read_bytes() == original
    assert updater.repository.get_entry_by_id("OLD").source_version is None
    assert _reload(tmp_path, "OLD").source_version is None
    assert not (tmp_path / "sports" / "auto_updated").exists()


def test_multiple_updates_replace_one_row_and_reload_latest_metadata(tmp_path, monkeypatch):
    updater = _updater(tmp_path, monkeypatch=monkeypatch)
    inserted = updater.apply_fact_update(_fact(), persist_markdown=True)

    for version in ("v2", "v3", "v4"):
        result = updater.apply_fact_update(
            _fact(source_version=version), persist_markdown=True,
        )
        assert result.action == KnowledgeUpdateAction.UPDATED

    target = tmp_path / "sports" / "auto_updated" / "auto_updated_knowledge.md"
    text = target.read_text(encoding="utf-8")
    assert text.count(f"| {inserted.entry_id} |") == 1
    assert _reload(tmp_path, inserted.entry_id).source_version == "v4"
