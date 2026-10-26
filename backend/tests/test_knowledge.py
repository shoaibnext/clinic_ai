from app.database.models import DocumentChunk
from app.services import knowledge_service


def _create_kb(client, clinic_headers, **extra):
    payload = {"name": "Clinic FAQ", "description": "General clinic information"}
    payload.update(extra)
    return client.post("/knowledge/bases", headers=clinic_headers, json=payload)


def _create_document(client, clinic_headers, kb_id, **extra):
    payload = {
        "knowledge_base_id": kb_id,
        "filename": "clinic_policy.txt",
        "content": (
            "ABC Clinic is open Monday to Friday from 9am to 5pm. "
            "A dental cleaning costs $50.\n\n"
            "Cancellation policy: please cancel at least 24 hours in advance."
        ),
    }
    payload.update(extra)
    return client.post("/knowledge/documents", headers=clinic_headers, json=payload)


def test_create_knowledge_base(client, clinic_headers):
    res = _create_kb(client, clinic_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Clinic FAQ"
    assert data["clinic_id"] is not None


def test_list_knowledge_bases(client, clinic_headers):
    assert client.get("/knowledge/bases", headers=clinic_headers).json() == []
    _create_kb(client, clinic_headers)
    assert len(client.get("/knowledge/bases", headers=clinic_headers).json()) == 1


def test_add_document(client, clinic_headers):
    kb = _create_kb(client, clinic_headers).json()
    res = _create_document(client, clinic_headers, kb["id"])
    assert res.status_code == 201
    data = res.json()
    assert data["filename"] == "clinic_policy.txt"
    # Ingestion may fail without an embedding provider; the document must still exist.
    assert data["status"] in {"pending", "processed", "failed"}


def test_add_document_unknown_kb(client, clinic_headers):
    res = _create_document(client, clinic_headers, 99999)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


def test_document_chunks_are_created(client, db_session, clinic, clinic_headers):
    kb = _create_kb(client, clinic_headers).json()
    long_content = "\n\n".join(
        f"Paragraph {i}: ABC Clinic offers high-quality dental services at affordable "
        f"prices. We specialize in cleaning, whitening, and orthodontics. "
        f"Bookings can be made by phone or WhatsApp." * 4
        for i in range(4)
    )
    assert _create_document(
        client, clinic_headers, kb["id"], content=long_content
    ).status_code == 201
    chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.clinic_id == clinic.id)
        .all()
    )
    assert len(chunks) >= 2
    assert all(c.content for c in chunks)
    combined = " ".join(c.content for c in chunks)
    assert "dental" in combined.lower()


def test_list_documents_and_filter(client, clinic_headers):
    kb1 = _create_kb(client, clinic_headers, name="KB One").json()
    kb2 = _create_kb(client, clinic_headers, name="KB Two").json()
    _create_document(client, clinic_headers, kb1["id"])
    _create_document(client, clinic_headers, kb2["id"])

    all_docs = client.get("/knowledge/documents", headers=clinic_headers).json()
    assert len(all_docs) == 2

    only_first = client.get(
        "/knowledge/documents", headers=clinic_headers, params={"knowledge_base_id": kb1["id"]}
    ).json()
    assert len(only_first) == 1
    assert only_first[0]["knowledge_base_id"] == kb1["id"]


def test_delete_document(client, db_session, clinic_headers):
    kb = _create_kb(client, clinic_headers).json()
    doc = _create_document(client, clinic_headers, kb["id"]).json()
    res = client.delete(f"/knowledge/documents/{doc['id']}", headers=clinic_headers)
    assert res.status_code == 204
    remaining = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc["id"]).all()
    assert remaining == []


def test_delete_document_not_found(client, clinic_headers):
    assert client.delete("/knowledge/documents/88888", headers=clinic_headers).status_code == 404


def test_tenant_isolation(client, clinic_headers, other_clinic_headers):
    kb = _create_kb(client, clinic_headers).json()
    doc = _create_document(client, clinic_headers, kb["id"]).json()
    # Clinic B sees no knowledge bases/documents and cannot delete Clinic A's document.
    assert client.get("/knowledge/bases", headers=other_clinic_headers).json() == []
    assert client.get("/knowledge/documents", headers=other_clinic_headers).json() == []
    assert client.delete(
        f"/knowledge/documents/{doc['id']}", headers=other_clinic_headers
    ).status_code == 404