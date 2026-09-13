import os
import pytest
from pathlib import Path

from app.services.knowledge_service import KnowledgeService
from app.repositories.knowledge_repository import KnowledgeRepository

# Helper to create temporary markdown files for tests
def create_md_file(tmp_path: Path, filename: str, rows: str):
    content = """# Temp Knowledge

---

| ID | Topic | Role | Intent | Question | Answer | Source | Classification |
|----|-------|------|--------|----------|--------|--------|----------------|
""" + rows + "\n---\n"
    file_path = tmp_path / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path

@pytest.fixture(scope="module")
def knowledge_repo(tmp_path_factory):
    # Create temporary knowledge directory mirroring the real one
    base = tmp_path_factory.mktemp("knowledge")
    # Copy existing customer.md to the temp dir for baseline entries
    original = Path(os.getenv("USERPROFILE")) / "Documents" / "AI" / "SportHub AI" / "docs" / "AI" / "knowledge" / "customer.md"
    if original.is_file():
        (base / "customer.md").write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    # Add admin‑only entry
    admin_rows = "| ADMIN-001 | Admin Guide | ADMIN | SYSTEM_GUIDE | How to manage system? | Admin can manage system via dashboard. | `ai_intent_router.py` (SYSTEM_GUIDE) | static |\n"
    create_md_file(base, "admin.md", admin_rows)
    # Add a dynamic entry (should be ignored)
    dynamic_rows = "| DYN-001 | Dynamic Test | CUSTOMER | CREATE_BOOKING | Dynamic booking test? | This is dynamic and should be ignored. | `ai_intent_router.py` (CREATE_BOOKING) | dynamic |\n"
    create_md_file(base, "dynamic.md", dynamic_rows)
    # Initialise repository pointing at this temp knowledge root
    repo = KnowledgeRepository(knowledge_root=str(base))
    return repo

def test_exact_question(knowledge_repo):
    service = KnowledgeService(repository=knowledge_repo)
    results = service.retrieve(query="SportHub là gì?", role="CUSTOMER", intent="SYSTEM_GUIDE")
    assert results
    entry, score = results[0]
    assert entry.id == "CUST-001"
    assert "SportHub là gì" in entry.question

def test_paraphrase(knowledge_repo):
    service = KnowledgeService(repository=knowledge_repo)
    # Slightly different phrasing
    results = service.retrieve(query="SportHub là gì vậy?", role="CUSTOMER", intent="SYSTEM_GUIDE")
    assert results
    entry, _ = results[0]
    assert entry.id == "CUST-001"

def test_role_filtering(knowledge_repo):
    service = KnowledgeService(repository=knowledge_repo)
    # ADMIN entry should not be returned for CUSTOMER role
    results = service.retrieve(query="How to manage system?", role="CUSTOMER", intent="SYSTEM_GUIDE")
    assert not results

def test_intent_filtering(knowledge_repo):
    service = KnowledgeService(repository=knowledge_repo)
    results = service.retrieve(query="Làm thế nào để đăng ký tài khoản?", role="CUSTOMER", intent="ACCOUNT_SUPPORT")
    assert results
    entry, _ = results[0]
    assert entry.id == "CUST-002"

def test_no_knowledge(knowledge_repo):
    service = KnowledgeService(repository=knowledge_repo)
    results = service.retrieve(query="Công thức làm bánh", role="CUSTOMER")
    assert not results

def test_out_of_scope(knowledge_repo):
    service = KnowledgeService(repository=knowledge_repo)
    results = service.retrieve(query="Any question", role="CUSTOMER", intent="OUT_OF_SCOPE")
    assert not results

def test_dynamic_entry_ignored(knowledge_repo):
    service = KnowledgeService(repository=knowledge_repo)
    results = service.retrieve(query="Dynamic booking test?", role="CUSTOMER", intent="CREATE_BOOKING")
    # The dynamic entry should be filtered out, leaving no result
    assert not results
