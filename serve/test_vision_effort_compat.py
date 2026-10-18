"""验证视觉标记和各 API 的思考档位，不需要 GPU。"""
import unittest
import struct
import tempfile
from pathlib import Path
from types import SimpleNamespace
from serve.server import Service, ByteTokenizer, model_settings


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

    def test_model_settings_preserve_family_effort_after_switch(self):
        # 上游将配置读取移到模型切换路径，默认档位必须在新入口保留。
        for family in ('glm5', 'joyai-llm', 'qwen'):
            svc = self.service(family)
            for level in ('low', 'high', 'max'):
                settings = model_settings({'reasoning_effort': level})
                svc.apply_settings(settings)
                expected = level if family != 'qwen' else settings['config_effort']
                self.assertEqual(svc.config_effort, expected)
            svc.apply_settings(model_settings({}))
            self.assertIsNone(svc.config_effort)

    def test_deepseek_image_alignment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.bin'
            rows = [(9.0, 9.0)] * 3 + [(float(i), float(i + 1)) for i in range(5)]
            payload = b''.join(struct.pack('<2f', *row) for row in rows)
            original = struct.pack('<5i', 0x31455653, 8, 8, 1, 2) + payload
            path.write_bytes(original)
            for position in range(8):
                with self.subTest(position=position):
                    aligned, count = Service.align_deepseek_image((path, 8), position)
                    shift = position % 4
                    data = aligned.read_bytes()
                    self.assertEqual(count, 8 - shift)
                    self.assertEqual(struct.unpack_from('<5i', data), (0x31455653, count, count, 1, 2))
                    self.assertEqual(data[20:], payload[shift * 8:])
                    self.assertEqual(path.read_bytes(), original)
                    # 起始标记后的第一个视觉行必须位于四 token 边界。
                    self.assertEqual((position + 3 - shift + 1) % 4, 0)

    def test_deepseek_alignment_rejects_unknown_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.bin'
            for data in (b'short', struct.pack('<5i', 0x31455653, 4, 2, 2, 1) + b'\0' * 16,
                         struct.pack('<5i', 0x31455653, 4, 4, 1, 1) + struct.pack('<4f', 1, 2, 3, 4)):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    Service.align_deepseek_image((path, 4), 1)


if __name__ == '__main__':
    unittest.main()
