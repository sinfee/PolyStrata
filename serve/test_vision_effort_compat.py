"""验证视觉标记和各 API 的思考档位，不需要 GPU。"""
import unittest
from types import SimpleNamespace
from serve.server import Service, ByteTokenizer


class VisionEffortCompatibility(unittest.TestCase):
    def service(self, family):
        tokenizer = ByteTokenizer()
        tokenizer.pre = family
        svc = Service.__new__(Service)
        svc.engine = SimpleNamespace()
        svc.template = SimpleNamespace(source='')
        svc._read_tokenizer(tokenizer)
        svc.config_effort = 'high'
        return svc

    def test_family_markers(self):
        expected = {'glm5': ('<|image|>', '<|begin_of_image|>', None),
                    'joyai-llm': ('<｜deepseek_image｜>', None, None)}
        for family, marks in expected.items():
            with self.subTest(family=family):
                self.assertEqual(self.service(family).image_marks, marks)

    def test_effort_across_apis(self):
        for family in ('glm5', 'joyai-llm'):
            svc = self.service(family)
            for level in ('low', 'high', 'max'):
                for req in ({'reasoning_effort': level}, {'reasoning': {'effort': level}},
                            {'output_config': {'effort': level}}, {'chat_template_kwargs': {'reasoning_effort': level}}):
                    with self.subTest(family=family, req=req):
                        self.assertEqual(svc.model_kwargs(req, {'reasoning_effort': 'xhigh'})['reasoning_effort'], level)
            self.assertEqual(svc.model_kwargs({}, {})['reasoning_effort'], 'high')
            self.assertEqual(svc.model_kwargs({'reasoning_effort': 'max'}, {'enable_thinking': False}), {'enable_thinking': False})
            self.assertEqual(svc.model_kwargs({'reasoning_effort': 'max', 'chat_template_kwargs': {'reasoning_effort': 'high'}}, {})['reasoning_effort'], 'high')

    def test_qwen_mapping_unchanged(self):
        svc = self.service('qwen')
        self.assertEqual(svc.model_kwargs({'reasoning_effort': 'high'}, {'reasoning_effort': 'xhigh'}), {'reasoning_effort': 'xhigh'})


if __name__ == '__main__':
    unittest.main()
