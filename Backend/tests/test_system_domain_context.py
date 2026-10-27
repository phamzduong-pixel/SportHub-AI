"""
Tests for CP-SYS-02 — SystemDomainContextService & AI Assistant Integration.
"""
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.facility import Facility, FacilityStatus
from app.models.field import Field
from app.models.product import FacilityProduct, ProductCatalogItem, ProductSport, ProductStatus
from app.models.user import User, UserRole
from app.repositories.ai_repository import AIRepository
from app.schemas.ai import AssistantMode
from app.services.ai_assistant_service import AIAssistantService
from app.services.product_service import ProductService
from app.services.system_domain_context_service import SystemDomainContextService


class TestSystemDomainContext(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        self.db = self.Session()

        # Seed test data
        self.fac1 = Facility(
            name="Sân Thể Thao Sao Mai",
            location="Hà Nội",
            status=FacilityStatus.APPROVED.value,
            is_active=True,
            sports=["bóng đá", "cầu lông"],
            amenities=["Bãi xe", "Wifi miễn phí", "Phòng thay đồ"],
            owner_id=1,
        )
        self.fac2 = Facility(
            name="CLB Pickleball Hà Nội",
            location="Hà Nội",
            status=FacilityStatus.APPROVED.value,
            is_active=True,
            sports=["pickleball"],
            amenities=["Điều hòa", "Nước uống miễn phí"],
            owner_id=1,
        )
        self.fac3 = Facility(
            name="Sân Chưa Duyệt",
            location="Hà Nội",
            status=FacilityStatus.PENDING_APPROVAL.value,
            is_active=True,
            sports=["bóng đá"],
            amenities=["Bãi xe ngầm"],
            owner_id=1,
        )
        self.db.add_all([self.fac1, self.fac2, self.fac3])
        self.db.commit()

        self.f1 = Field(name="Sân Bóng Đá 1", facility_id=self.fac1.id, sport_type="bóng đá", location="Hà Nội", capacity=10, base_price=100000, status="available", amenities=["Đèn chiếu sáng"])
        self.f2 = Field(name="Sân Cầu Lông A", facility_id=self.fac1.id, sport_type="cầu lông", location="Hà Nội", capacity=4, base_price=100000, status="available", amenities=["Thảm chống trượt"])
        self.f3 = Field(name="Sân Pickleball P1", facility_id=self.fac2.id, sport_type="pickleball", location="Hà Nội", capacity=4, base_price=100000, status="available", amenities=["Lưới chuẩn quốc tế"])
        self.f4 = Field(name="Sân Chưa Duyệt 1", facility_id=self.fac3.id, sport_type="bóng đá", location="Hà Nội", capacity=10, base_price=100000, status="available", amenities=["Cỏ nhân tạo 5cm"])
        self.db.add_all([self.f1, self.f2, self.f3, self.f4])
        self.db.commit()

        self.p1 = FacilityProduct(
            facility_id=self.fac1.id,
            name="Thuê Áo Nối (Bít-búp)",
            product_type="Dịch vụ",
            price=10000,
            unit="bộ",
            status=ProductStatus.ACTIVE.value,
            track_inventory=True,
            stock_quantity=50,
            reserved_quantity=5,
        )
        self.p2 = FacilityProduct(
            facility_id=self.fac1.id,
            name="Nước Suối Lavie 500ml",
            product_type="Hàng hóa",
            price=10000,
            unit="chai",
            status=ProductStatus.ACTIVE.value,
            track_inventory=False,
        )
        self.p3 = FacilityProduct(
            facility_id=self.fac2.id,
            name="Cho Thuê Vợt Pickleball High-End",
            product_type="Dịch vụ",
            price=30000,
            unit="giờ",
            status=ProductStatus.ACTIVE.value,
            track_inventory=True,
            stock_quantity=10,
        )
        self.p4 = FacilityProduct(
            facility_id=self.fac1.id,
            name="Bóng Đá Động Lực (Cũ)",
            product_type="Dịch vụ",
            price=20000,
            unit="quả",
            status=ProductStatus.INACTIVE.value,
        )
        self.db.add_all([self.p1, self.p2, self.p3, self.p4])
        self.db.commit()

        ps1 = ProductSport(product_id=self.p1.id, sport_name="bóng đá")
        ps2 = ProductSport(product_id=self.p2.id, sport_name="Dùng chung")
        ps3 = ProductSport(product_id=self.p3.id, sport_name="pickleball")
        ps4 = ProductSport(product_id=self.p4.id, sport_name="bóng đá")
        self.db.add_all([ps1, ps2, ps3, ps4])
        self.db.commit()

        cat1 = ProductCatalogItem(
            catalog_key="football-goalkeeper-gloves",
            name="Găng tay thủ môn",
            product_type="Dịch vụ",
            unit="đôi",
            sport_name="bóng đá",
            is_active=True,
            sort_order=1,
        )
        cat2 = ProductCatalogItem(
            catalog_key="tennis-wrist-wrap",
            name="Băng quấn cổ tay",
            product_type="Hàng hóa",
            unit="cái",
            sport_name="tennis",
            is_active=True,
            sort_order=1,
        )
        cat3 = ProductCatalogItem(
            catalog_key="badminton-racket-rental",
            name="Thuê vợt cầu lông",
            product_type="Dịch vụ",
            unit="cây",
            sport_name="cầu lông",
            is_active=True,
            sort_order=1,
        )
        cat4 = ProductCatalogItem(
            catalog_key="basketball-ball-rental",
            name="Thuê bóng rổ",
            product_type="Dịch vụ",
            unit="quả",
            sport_name="bóng rổ",
            is_active=True,
            sort_order=1,
        )
        cat5 = ProductCatalogItem(
            catalog_key="volleyball-ball-rental",
            name="Thuê bóng chuyền",
            product_type="Dịch vụ",
            unit="quả",
            sport_name="bóng chuyền",
            is_active=True,
            sort_order=1,
        )
        self.db.add_all([cat1, cat2, cat3, cat4, cat5])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_get_sport_products_live(self):
        """Test retrieving live products for a sport."""
        svc = SystemDomainContextService(self.db)
        res = svc.get_sport_products("bóng đá")

        self.assertEqual(res.sport, "bóng đá")
        self.assertEqual(res.source, "live")
        self.assertEqual(res.contributing_facility_count, 1)
        names = [p.name for p in res.live_products]
        self.assertIn("Thuê Áo Nối (Bít-búp)", names)
        self.assertIn("Nước Suối Lavie 500ml", names)
        self.assertNotIn("Bóng Đá Động Lực (Cũ)", names)

    def test_get_sport_products_includes_live_shared_products_for_tennis(self):
        """A live product linked to Dùng chung applies to tennis as well."""
        svc = SystemDomainContextService(self.db)
        res = svc.get_sport_products("tennis")

        self.assertEqual(res.sport, "tennis")
        self.assertEqual(res.source, "live")
        self.assertIn("Nước Suối Lavie 500ml", [item.name for item in res.live_products])
        self.assertEqual(res.catalog_items, [])

    def test_get_sport_amenities_restricted_aggregation(self):
        """
        CP-SYS-02 Rule 1: get_sport_amenities MUST only aggregate amenities from
        facilities/fields confirmed to support that sport.
        """
        svc = SystemDomainContextService(self.db)

        res_football = svc.get_sport_amenities("bóng đá")
        self.assertTrue(res_football.has_data)
        self.assertIn("Bãi xe", res_football.amenities)
        self.assertIn("Đèn chiếu sáng", res_football.amenities)
        self.assertNotIn("Điều hòa", res_football.amenities)
        self.assertNotIn("Lưới chuẩn quốc tế", res_football.amenities)
        self.assertNotIn("Cỏ nhân tạo 5cm", res_football.amenities)

        res_pickleball = svc.get_sport_amenities("pickleball")
        self.assertIn("Điều hòa", res_pickleball.amenities)
        self.assertIn("Lưới chuẩn quốc tế", res_pickleball.amenities)
        self.assertNotIn("Đèn chiếu sáng", res_pickleball.amenities)

    def test_get_venue_amenities(self):
        """Test field + facility amenity union for a specific venue."""
        svc = SystemDomainContextService(self.db)
        res = svc.get_venue_amenities(self.f1.id)

        self.assertIsNotNone(res)
        self.assertEqual(res.field_name, "Sân Bóng Đá 1")
        self.assertIn("Đèn chiếu sáng", res.field_amenities)
        self.assertIn("Wifi miễn phí", res.facility_amenities)
        self.assertIn("Bãi xe", res.all_amenities)

    def test_ai_assistant_system_domain_natural_mode(self):
        """Test AI assistant query handling in Natural mode."""
        repo = AIRepository(self.db)
        user = User(email="test@user.com", role=UserRole.CUSTOMER, id=10)
        service = AIAssistantService(repo, current_user=user)

        resp = service.ask("Môn bóng đá có những tiện ích gì?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(resp["status"], "OK")
        football_options = ProductService(self.db).sport_product_names("Bóng đá")
        for option in football_options:
            self.assertIn(option, resp["reply"])
        self.assertNotIn("Bãi xe", resp["reply"])
        self.assertNotIn("Phòng thay đồ", resp["reply"])
        self.assertEqual(resp["understood"]["domain_context_type"], "sport_amenities")

        resp2 = service.ask("Môn pickleball có tiện ích gì?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(resp2["status"], "OK")
        self.assertIn("Cho Thuê Vợt Pickleball High-End", resp2["reply"])
        self.assertNotIn("Điều hòa", resp2["reply"])
        self.assertIn("đồng bộ với tùy chọn theo môn trên Tìm sân", resp2["reply"])
        self.assertEqual(resp2["understood"]["domain_context_type"], "sport_amenities")

    def test_find_sport_options_are_the_assistant_amenity_source_for_all_sports(self):
        repo = AIRepository(self.db)
        service = AIAssistantService(repo)
        product_service = ProductService(self.db)
        sports = ("Bóng đá", "Cầu lông", "Pickleball", "Tennis", "Bóng rổ", "Bóng chuyền")

        for sport in sports:
            with self.subTest(sport=sport):
                options = product_service.sport_product_names(sport)
                self.assertTrue(options)
                response = service.ask(
                    f"Môn {sport} có những tiện ích gì?",
                    assistant_mode=AssistantMode.NATURAL,
                )
                self.assertEqual(response["status"], "OK")
                self.assertEqual(response["understood"]["domain_context_type"], "sport_amenities")
                for option in options:
                    self.assertIn(option, response["reply"])
                for physical_feature in ("Bãi xe", "Điều hòa", "Đèn chiếu sáng", "Phòng thay đồ"):
                    self.assertNotIn(physical_feature, response["reply"])

    def test_venue_amenity_queries_separate_orderable_options_from_facility_features(self):
        repo = AIRepository(self.db)
        service = AIAssistantService(repo)

        orderable_query = "Sân Bóng Đá 1 có tiện ích gì?"
        kind, sport, field_id = service._detect_system_domain_query(
            orderable_query, {"field_id": self.f1.id},
        )
        self.assertEqual(kind, "venue_orderable_options")
        self.assertEqual(field_id, self.f1.id)
        orderable = service._answer_system_domain(orderable_query, kind, sport, field_id, {})
        self.assertIn("Thuê Áo Nối (Bít-búp)", orderable["reply"])
        self.assertNotIn("Bãi xe", orderable["reply"])
        self.assertEqual(orderable["understood"]["domain_context_type"], "venue_orderable_options")

        service_query = "Sân Bóng Đá 1 có dịch vụ nào để chọn khi đặt?"
        service_kind, service_sport, service_field_id = service._detect_system_domain_query(
            service_query, {"field_id": self.f1.id},
        )
        self.assertEqual(service_kind, "venue_orderable_options")
        self.assertIn(
            "Thuê Áo Nối (Bít-búp)",
            service._answer_system_domain(
                service_query, service_kind, service_sport, service_field_id, {},
            )["reply"],
        )
        followup_kind, followup_sport, followup_field_id = service._detect_system_domain_query(
            "Còn cái nào nữa?",
            {
                "domain_context_type": "venue_orderable_options",
                "field_id": self.f1.id,
                "sport_type": "Bóng đá",
            },
        )
        self.assertEqual(followup_kind, "venue_orderable_options")
        self.assertEqual(followup_sport, "Bóng đá")
        self.assertEqual(followup_field_id, self.f1.id)

        feature_query = "Sân Bóng Đá 1 có bãi xe không?"
        feature_kind, feature_sport, feature_field_id = service._detect_system_domain_query(
            feature_query, {"field_id": self.f1.id},
        )
        self.assertEqual(feature_kind, "venue_amenities")
        service._assistant_mode = AssistantMode.PROFESSIONAL
        features = service._answer_system_domain(
            feature_query, feature_kind, feature_sport, feature_field_id, {},
        )
        self.assertIn("Cơ sở vật chất", features["reply"])
        self.assertIn("Bãi xe", features["reply"])
        self.assertIn("không phải sản phẩm/dịch vụ có thể đặt kèm", features["reply"])

    def test_followup_keeps_physical_feature_context_separate(self):
        service = AIAssistantService(AIRepository(self.db))
        context = {
            "domain_context_type": "sport_facility_features",
            "sport_type": "Bóng đá",
        }
        kind, sport, field_id = service._detect_system_domain_query("Còn môn cầu lông thì sao?", context)
        self.assertEqual(kind, "sport_facility_features")
        self.assertEqual(sport, "cầu lông")
        self.assertIsNone(field_id)

    def test_amenity_query_without_sport_asks_for_sport_instead_of_assuming_football(self):
        service = AIAssistantService(AIRepository(self.db))
        response = service.ask("Tiện ích có gì?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(response["status"], "NEED_MORE_DATA")
        self.assertIn("môn thể thao nào", response["reply"])

        capability = service.ask("Bạn giúp được gì?", assistant_mode=AssistantMode.NATURAL)
        self.assertNotEqual(capability["understood"].get("domain_context_type"), "sport_amenities")

    def test_ai_assistant_system_domain_professional_mode(self):
        """Test AI assistant query handling in Professional mode."""
        repo = AIRepository(self.db)
        user = User(email="prof@user.com", role=UserRole.CUSTOMER, id=11)
        service = AIAssistantService(repo, current_user=user)

        resp = service.ask("Môn tennis có những tiện ích gì?", assistant_mode=AssistantMode.PROFESSIONAL)
        self.assertEqual(resp["status"], "OK")
        tennis_options = ProductService(self.db).sport_product_names("Tennis")
        for option in tennis_options:
            self.assertIn(option, resp["reply"])
        self.assertNotIn("Bãi xe", resp["reply"])
        self.assertNotIn("Điều hòa", resp["reply"])
        self.assertEqual(resp["understood"]["domain_context_type"], "sport_amenities")


if __name__ == "__main__":
    unittest.main()
