import unittest
from pathlib import Path


class AIAssistantUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        page = Path(__file__).parents[2] / 'Frontend' / 'src' / 'pages' / 'AIAssistantPage.tsx'
        cls.source = page.read_text(encoding='utf-8')

    def test_no_result_does_not_render_duplicate_message(self):
        self.assertNotIn(
            'Không có cơ sở phù hợp trong dữ liệu SportHub hiện tại.',
            self.source,
        )
        self.assertNotIn('message.noResult', self.source)

    def test_no_result_can_render_quick_actions(self):
        self.assertIn("response.status !== 'NO_RESULT'", self.source)
        self.assertIn('Tìm khu vực khác', self.source)
        self.assertIn('Xem tất cả cơ sở', self.source)
        self.assertIn('Đổi môn thể thao', self.source)

    def test_new_search_replaces_old_empty_state(self):
        self.assertIn('current.map(clearInteractiveContent)', self.source)
        self.assertIn('quickActions: undefined', self.source)

    def test_out_of_scope_clears_previous_results(self):
        self.assertIn("response.classification === 'OUT_OF_SCOPE'", self.source)
        self.assertIn('current.map(clearInteractiveContent)', self.source)

    def test_partner_approval_refreshes_frontend_role(self):
        page = Path(__file__).parents[2] / 'Frontend' / 'src' / 'pages' / 'PartnerApplicationPage.tsx'
        source = page.read_text(encoding='utf-8')
        self.assertIn("application?.status === 'APPROVED'", source)
        self.assertIn('refreshUser()', source)

    def test_missing_hotline_is_not_rendered_as_demo_phone(self):
        page = Path(__file__).parents[2] / 'Frontend' / 'src' / 'components' / 'venue' / 'VenueDetailTabs.tsx'
        source = page.read_text(encoding='utf-8')
        self.assertNotIn("venue.hotline || '0901 234 567'", source)
        self.assertIn('Cơ sở chưa cấu hình hotline.', source)


if __name__ == '__main__':
    unittest.main()
