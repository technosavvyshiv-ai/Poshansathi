"""Phase 10 welfare-scheme tests: rules, links, status, recommendations, routes."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import (
    AnganwadiCentre,
    Beneficiary,
    BeneficiaryScheme,
    Child,
    Mother,
    User,
    WelfareScheme,
)
from app.services import scheme_service
from app.utils.constants import (
    BeneficiaryType,
    Gender,
    RecordStatus,
    SchemeStatus,
    UserRole,
)
from app.utils.scheme_rules import BeneficiaryProfile, evaluate
from app.utils.validators import ValidationError

PASSWORD = "password123"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Scheme Centre A", code="SCA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Scheme Centre B", code="SCB-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def make_user(db):
    def make(username, role=UserRole.AWW, centre=None, is_active=True):
        user = User(
            full_name=f"Test {username}",
            username=username,
            role=role,
            centre=centre,
            is_active=is_active,
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return user

    return make


@pytest.fixture()
def make_child(db):
    def make(centre, name="Scheme Child", age_years=2):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.CHILD,
            full_name=name,
            date_of_birth=date.today() - timedelta(days=365 * age_years),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=date.today(),
        )
        child = Child(beneficiary=beneficiary)
        db.session.add(child)
        db.session.commit()
        return child

    return make


@pytest.fixture()
def make_mother(db):
    def make(centre, name="Scheme Mother", mother_type=BeneficiaryType.PREGNANT_WOMAN):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=mother_type,
            full_name=name,
            date_of_birth=date.today() - timedelta(days=365 * 25),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=date.today(),
        )
        mother = Mother(beneficiary=beneficiary)
        db.session.add(mother)
        db.session.commit()
        return mother

    return make


@pytest.fixture()
def make_scheme(db):
    def make(name="Demo Scheme", category="Child Welfare", **overrides):
        scheme = WelfareScheme(
            name=name, category=category, is_active=True, **overrides
        )
        db.session.add(scheme)
        db.session.commit()
        return scheme

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def scheme_form(**overrides):
    data = {
        "name": "New Demo Scheme",
        "category": "Child Welfare",
        "target_group": "Children under 6",
        "description": "Demo scheme description.",
        "benefits": "Supplementary nutrition.",
        "eligibility": "Project demonstration information only.",
        "required_documents": "MCP card.",
        "application_info": "Register at the centre.",
        "is_active": "on",
    }
    data.update(overrides)
    return data


def link_form(scheme, **overrides):
    data = {
        "scheme_id": str(scheme.id),
        "status": SchemeStatus.ELIGIBLE.value,
        "applied_date": date.today().isoformat(),
        "notes": "Recorded during a demo visit.",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Relevance rule unit tests
# ---------------------------------------------------------------------------
def test_child_welfare_rule_matches_child_and_mother():
    child = BeneficiaryProfile(BeneficiaryType.CHILD, age_years=2)
    mother = BeneficiaryProfile(BeneficiaryType.PREGNANT_WOMAN)

    assert evaluate(child, "Child Welfare").matched is True
    assert evaluate(mother, "Child Welfare").matched is True


def test_maternity_rule_only_matches_mothers():
    child = BeneficiaryProfile(BeneficiaryType.CHILD, age_years=2)
    mother = BeneficiaryProfile(BeneficiaryType.LACTATING_MOTHER)

    assert evaluate(child, "Maternity Benefit").matched is False
    assert evaluate(mother, "Maternity Benefit").matched is True


def test_school_nutrition_rule_requires_age_three():
    younger = BeneficiaryProfile(BeneficiaryType.CHILD, age_years=2)
    older = BeneficiaryProfile(BeneficiaryType.CHILD, age_years=4)

    assert evaluate(younger, "School Nutrition").matched is False
    assert evaluate(older, "School Nutrition").matched is True


def test_health_rule_only_matches_children():
    child = BeneficiaryProfile(BeneficiaryType.CHILD, age_years=2)
    mother = BeneficiaryProfile(BeneficiaryType.PREGNANT_WOMAN)

    assert evaluate(child, "Health").matched is True
    assert evaluate(mother, "Health").matched is False


def test_unknown_category_never_matches():
    profile = BeneficiaryProfile(BeneficiaryType.CHILD, age_years=2)
    relevance = evaluate(profile, "Unconfigured Category")

    assert relevance.matched is False
    assert "No configured relevance" in relevance.reason


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------
def test_scheme_name_must_be_unique(db, make_scheme):
    make_scheme(name="Duplicate Scheme")

    with pytest.raises(ValidationError):
        scheme_service.create_scheme(scheme_form(name="duplicate scheme"))


def test_link_scheme_and_duplicate_prevention(db, centre, make_child, make_scheme):
    child = make_child(centre)
    scheme = make_scheme()

    link = scheme_service.link_scheme(child.beneficiary, scheme, link_form(scheme))
    assert link.status == SchemeStatus.ELIGIBLE

    with pytest.raises(ValidationError):
        scheme_service.link_scheme(child.beneficiary, scheme, link_form(scheme))
    assert BeneficiaryScheme.query.count() == 1


def test_relevant_schemes_excludes_linked_and_non_matching(
    db, centre, make_child, make_scheme
):
    child = make_child(centre)
    matching = make_scheme(name="Child Welfare Scheme", category="Child Welfare")
    non_matching = make_scheme(name="Maternity Scheme", category="Maternity Benefit")

    rows = scheme_service.relevant_schemes(child.beneficiary)
    ids = {row["scheme"].id for row in rows}
    assert matching.id in ids
    assert non_matching.id not in ids

    scheme_service.link_scheme(
        child.beneficiary, matching, link_form(matching)
    )
    rows = scheme_service.relevant_schemes(child.beneficiary)
    assert matching.id not in {row["scheme"].id for row in rows}


def test_update_link_status_and_unlink(db, centre, make_child, make_scheme):
    child = make_child(centre)
    scheme = make_scheme()
    link = scheme_service.link_scheme(child.beneficiary, scheme, link_form(scheme))

    scheme_service.update_link(
        link,
        link_form(
            scheme,
            status=SchemeStatus.ENROLLED.value,
            notes="Enrolment confirmed.",
        ),
    )
    refreshed = db.session.get(BeneficiaryScheme, link.id)
    assert refreshed.status == SchemeStatus.ENROLLED
    assert refreshed.notes == "Enrolment confirmed."

    scheme_service.unlink(refreshed)
    assert BeneficiaryScheme.query.count() == 0


def test_status_counts_are_centre_scoped(
    db, centre, other_centre, make_child, make_scheme
):
    own = make_child(centre, name="Own Child")
    outsider = make_child(other_centre, name="Other Child")
    scheme = make_scheme()
    scheme_service.link_scheme(own.beneficiary, scheme, link_form(scheme))
    scheme_service.link_scheme(
        outsider.beneficiary,
        scheme,
        link_form(scheme, status=SchemeStatus.APPLIED.value),
    )

    scoped = scheme_service.status_counts(scope_centre_id=centre.id)
    assert scoped["TOTAL"] == 1
    assert scoped[SchemeStatus.ELIGIBLE.value] == 1
    assert scoped[SchemeStatus.APPLIED.value] == 0


# ---------------------------------------------------------------------------
# Catalogue routes
# ---------------------------------------------------------------------------
def test_schemes_require_login(client, db):
    response = client.get("/schemes/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_catalogue_lists_and_filters(client, db, make_user, make_scheme):
    make_scheme(name="Child Scheme", category="Child Welfare")
    make_scheme(name="Maternity Scheme", category="Maternity Benefit")
    make_user("aww_scheme", role=UserRole.AWW)
    login(client, "aww_scheme")

    response = client.get("/schemes/?category=Child+Welfare")

    assert response.status_code == 200
    assert b"Child Scheme" in response.data
    assert b"Maternity Scheme" not in response.data


def test_scheme_detail_page(client, db, make_user, make_scheme):
    scheme = make_scheme(
        name="Detail Scheme",
        benefits="Food support.",
        required_documents="MCP card.",
    )
    make_user("aww_scheme", role=UserRole.AWW)
    login(client, "aww_scheme")

    response = client.get(f"/schemes/{scheme.id}")

    assert response.status_code == 200
    assert b"Detail Scheme" in response.data
    assert b"Food support." in response.data


def test_admin_can_create_scheme(client, db, make_user):
    make_user("admin_scheme", role=UserRole.ADMIN)
    login(client, "admin_scheme")

    response = client.post("/schemes/new", data=scheme_form())

    assert response.status_code == 302
    assert WelfareScheme.query.filter_by(name="New Demo Scheme").count() == 1


def test_aww_cannot_create_scheme(client, db, make_user):
    make_user("aww_scheme", role=UserRole.AWW)
    login(client, "aww_scheme")

    response = client.post("/schemes/new", data=scheme_form())

    assert response.status_code == 403
    assert WelfareScheme.query.count() == 0


def test_scheme_validation_requires_name(client, db, make_user):
    make_user("admin_scheme", role=UserRole.ADMIN)
    login(client, "admin_scheme")

    response = client.post("/schemes/new", data=scheme_form(name=""))

    assert response.status_code == 400
    assert b"Scheme name is required" in response.data
    assert WelfareScheme.query.count() == 0


def test_admin_can_edit_scheme(client, db, make_user, make_scheme):
    scheme = make_scheme(name="Editable Scheme")
    make_user("admin_scheme", role=UserRole.ADMIN)
    login(client, "admin_scheme")

    response = client.post(
        f"/schemes/{scheme.id}/edit",
        data=scheme_form(name="Edited Scheme", benefits="Updated benefits."),
    )

    assert response.status_code == 302
    refreshed = db.session.get(WelfareScheme, scheme.id)
    assert refreshed.name == "Edited Scheme"
    assert refreshed.benefits == "Updated benefits."


# ---------------------------------------------------------------------------
# Beneficiary scheme history / links
# ---------------------------------------------------------------------------
def test_beneficiary_schemes_page_shows_recommendations(
    client, db, centre, make_user, make_child, make_scheme
):
    child = make_child(centre)
    make_scheme(name="Recommended Scheme", category="Child Welfare")
    make_scheme(name="Not Relevant Scheme", category="Maternity Benefit")
    make_user("aww_scheme", role=UserRole.AWW, centre=centre)
    login(client, "aww_scheme")

    response = client.get(f"/beneficiaries/{child.beneficiary_id}/schemes")

    assert response.status_code == 200
    assert b"Recommended Scheme" in response.data
    # The relevance reason is only rendered for matched recommendations.
    assert b"Child under 6 years" in response.data
    assert b"Potentially relevant" in response.data
    assert b"official eligibility" in response.data


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_cannot_manage_links(
    client, db, centre, make_user, make_child, make_scheme, role
):
    child = make_child(centre)
    scheme = make_scheme()
    make_user("reader", role=role)
    login(client, "reader")

    assert client.get(f"/beneficiaries/{child.beneficiary_id}/schemes").status_code == 200
    assert (
        client.post(
            f"/beneficiaries/{child.beneficiary_id}/schemes/link",
            data=link_form(scheme),
        ).status_code
        == 403
    )


def test_aww_can_link_and_update_and_unlink(
    client, db, centre, make_user, make_child, make_scheme
):
    child = make_child(centre)
    scheme = make_scheme(name="Workflow Scheme")
    make_user("aww_scheme", role=UserRole.AWW, centre=centre)
    login(client, "aww_scheme")

    response = client.post(
        f"/beneficiaries/{child.beneficiary_id}/schemes/link",
        data=link_form(scheme),
    )
    assert response.status_code == 302
    link = BeneficiaryScheme.query.filter_by(
        beneficiary_id=child.beneficiary_id
    ).one()

    response = client.post(
        f"/beneficiaries/{child.beneficiary_id}/schemes/{link.id}/update",
        data=link_form(scheme, status=SchemeStatus.APPLIED.value),
    )
    assert response.status_code == 302
    assert db.session.get(BeneficiaryScheme, link.id).status == SchemeStatus.APPLIED

    response = client.post(
        f"/beneficiaries/{child.beneficiary_id}/schemes/{link.id}/unlink"
    )
    assert response.status_code == 302
    assert BeneficiaryScheme.query.count() == 0


def test_duplicate_link_is_rejected(client, db, centre, make_user, make_child, make_scheme):
    child = make_child(centre)
    scheme = make_scheme()
    make_user("aww_scheme", role=UserRole.AWW, centre=centre)
    login(client, "aww_scheme")

    client.post(
        f"/beneficiaries/{child.beneficiary_id}/schemes/link", data=link_form(scheme)
    )
    response = client.post(
        f"/beneficiaries/{child.beneficiary_id}/schemes/link", data=link_form(scheme)
    )

    assert response.status_code == 302
    assert BeneficiaryScheme.query.count() == 1


def test_link_requires_a_valid_scheme(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_scheme", role=UserRole.AWW, centre=centre)
    login(client, "aww_scheme")

    response = client.post(
        f"/beneficiaries/{child.beneficiary_id}/schemes/link",
        data={"scheme_id": "", "status": SchemeStatus.ELIGIBLE.value},
    )

    assert response.status_code == 302
    assert BeneficiaryScheme.query.count() == 0


def test_aww_cannot_access_other_centre_beneficiary_schemes(
    client, db, centre, other_centre, make_user, make_child
):
    other = make_child(other_centre, name="Other Child")
    make_user("aww_scheme", role=UserRole.AWW, centre=centre)
    login(client, "aww_scheme")

    assert (
        client.get(f"/beneficiaries/{other.beneficiary_id}/schemes").status_code == 403
    )


def test_beneficiary_detail_links_to_schemes(
    client, db, centre, make_user, make_child
):
    child = make_child(centre)
    make_user("aww_scheme", role=UserRole.AWW, centre=centre)
    login(client, "aww_scheme")

    response = client.get(f"/beneficiaries/{child.beneficiary_id}")

    assert response.status_code == 200
    assert f"/beneficiaries/{child.beneficiary_id}/schemes".encode() in response.data


def test_full_scheme_workflow(client, db, centre, make_user, make_child):
    """ADMIN creates a scheme; AWW links, updates and unlinks for a child."""
    child = make_child(centre)
    make_user("admin_scheme", role=UserRole.ADMIN)
    make_user("aww_scheme", role=UserRole.AWW, centre=centre)

    # ADMIN creates the scheme.
    login(client, "admin_scheme")
    client.post(
        "/schemes/new",
        data=scheme_form(name="Workflow Created Scheme", category="Child Welfare"),
    )
    scheme = WelfareScheme.query.filter_by(name="Workflow Created Scheme").one()

    # AWW sees it as potentially relevant and links the child.
    login(client, "aww_scheme")
    page = client.get(f"/beneficiaries/{child.beneficiary_id}/schemes")
    assert b"Workflow Created Scheme" in page.data

    client.post(
        f"/beneficiaries/{child.beneficiary_id}/schemes/link",
        data=link_form(scheme, status=SchemeStatus.APPLIED.value),
    )
    link = BeneficiaryScheme.query.filter_by(scheme_id=scheme.id).one()
    assert link.status == SchemeStatus.APPLIED

    # History shows the association; unlink removes it.
    history = client.get(f"/beneficiaries/{child.beneficiary_id}/schemes")
    assert b"Workflow Created Scheme" in history.data

    client.post(
        f"/beneficiaries/{child.beneficiary_id}/schemes/{link.id}/unlink"
    )
    assert BeneficiaryScheme.query.count() == 0
