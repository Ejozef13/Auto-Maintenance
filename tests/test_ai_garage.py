"""AI tests run offline, without a GPU, Ollama, ComfyUI, or a display."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_garage import (AIStore, answer_question, endpoint, generate_portrait,
                       portrait_prompt, prepare_workflow, search_web)


class AITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = AIStore(self.root / 'ai_data')
        self.car = {'id': 'civic', 'name': '2015 Honda Civic', 'notes': 'PRIVATE VIN', 'mileage': 85000, 'records': []}
        self.settings = self.store.settings()

    def manual(self, text, car_id='civic', name='owners.txt'):
        path = self.root / name
        path.write_text(text, encoding='utf-8')
        self.store.import_manual(car_id, path)

    def test_manual_pages_and_car_isolation(self):
        self.manual('Audio controls on dashboard.\fEngine oil capacity is 3.9 quarts.')
        self.manual('Engine oil capacity is 7 quarts.', 'truck')
        passages = self.store.retrieve('civic', 'What is my engine oil capacity?')
        self.assertEqual(passages[0]['page'], 2)
        self.assertIn('3.9', passages[0]['text'])
        self.assertNotIn('7 quarts', str(passages))
        self.assertEqual(self.store.retrieve('other', 'oil'), [])

    def test_real_pdf_extraction_and_page_references(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        except ImportError:
            self.skipTest('Optional pypdf dependency not installed')
        writer = PdfWriter()
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        for text in ['Audio dashboard controls.', 'Engine oil viscosity is 0W-20.']:
            page = writer.add_blank_page(width=600, height=800)
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(f'BT /F1 12 Tf 50 700 Td ({text}) Tj ET'.encode())
            page[NameObject('/Contents')] = writer._add_object(stream)
        path = self.root / 'owners.pdf'
        with path.open('wb') as output:
            writer.write(output)
        self.store.import_manual('civic', path)
        result = self.store.retrieve('civic', 'oil viscosity')
        self.assertEqual(result[0]['page'], 2)
        self.assertIn('0W-20', result[0]['text'])

    def test_reimport_replaces_same_file_and_removal_is_scoped(self):
        self.manual('Oil old value')
        self.manual('Oil new value')
        self.manual('Oil other car', 'truck')
        self.assertEqual(len(self.store.retrieve('civic', 'oil')), 1)
        self.assertIn('new', self.store.retrieve('civic', 'oil')[0]['text'])
        self.store.remove_manuals('civic')
        self.assertEqual(self.store.manuals('civic'), [])
        self.assertTrue(self.store.manuals('truck'))

    def test_empty_manual_does_not_destroy_existing_index(self):
        self.manual('Engine oil specification.')
        with self.assertRaisesRegex(ValueError, 'No text'):
            self.manual('')
        self.assertTrue(self.store.retrieve('civic', 'oil'))

    def test_fts_operators_and_sql_are_not_executed(self):
        self.manual('Engine oil specification.')
        for question in ['" OR * NOT )', "oil'; DROP TABLE chunks; --", 'the is my']:
            self.store.retrieve('civic', question)
        self.assertTrue(self.store.retrieve('civic', 'oil'))

    def test_settings_validation_and_persistence(self):
        settings = {**self.settings, 'chat_model': 'gpt-oss:20b'}
        self.store.save_settings(settings)
        self.assertEqual(self.store.settings()['chat_model'], 'gpt-oss:20b')
        with self.assertRaises(ValueError):
            self.store.save_settings({**settings, 'ollama_url': 'file:///etc/passwd'})
        self.assertEqual(self.store.settings()['chat_model'], 'gpt-oss:20b')
        for bad in ['http://user:password@localhost', 'http://localhost/?token=x', 'localhost:11434']:
            with self.assertRaises(ValueError):
                endpoint(bad)

    def test_bad_settings_are_not_silently_overwritten(self):
        (self.store.directory / 'settings.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'unreadable'):
            self.store.settings()

    @patch('ai_garage.request_json')
    def test_rag_prompt_contains_evidence_history_and_selected_car(self, request):
        self.manual('Oil capacity is 3.9 quarts.')
        request.return_value = {'message': {'content': 'The manual says 3.9 quarts [M1].'}}
        response = answer_question(self.store, self.settings, self.car, 'oil capacity?', [{'role': 'user', 'content': 'Tell me about oil.'}])
        payload = request.call_args.args[1]
        self.assertFalse(payload['stream'])
        self.assertIn('3.9', payload['messages'][1]['content'])
        self.assertIn('2015 Honda Civic', payload['messages'][1]['content'])
        self.assertEqual(payload['messages'][-1]['content'], 'oil capacity?')
        self.assertEqual(response['sources'][0]['id'], 'M1')
        self.assertEqual(response['warning'], '')

    @patch('ai_garage.request_json')
    def test_no_evidence_and_unknown_citation_are_visible(self, request):
        request.return_value = {'message': {'content': 'Made up [M999]'}}
        result = answer_question(self.store, self.settings, self.car, 'torque?')
        self.assertEqual(result['sources'], [])
        self.assertIn('unknown citation', result['warning'])

    @patch('ai_garage.request_json')
    def test_web_disabled_makes_only_chat_request(self, request):
        request.return_value = {'message': {'content': 'General car discussion.'}}
        answer_question(self.store, self.settings, self.car, 'hello')
        self.assertEqual(request.call_count, 1)
        self.assertTrue(request.call_args.args[0].endswith('/api/chat'))

    @patch('ai_garage.request_json')
    def test_web_failure_keeps_manual_answer_and_reports_failure(self, request):
        request.return_value = {'message': {'content': 'No web available.'}}
        result = answer_question(self.store, self.settings, self.car, 'hello', use_web=True)
        self.assertIn('Web search unavailable', result['warning'])
        self.assertEqual(request.call_count, 1)

    @patch('ai_garage.request_json')
    def test_web_sources_and_query_privacy(self, request):
        request.return_value = {'results': [{'title': 'Manufacturer', 'url': 'https://example.com/manual', 'content': 'Engine oil specification.'}, {'url': 'javascript:alert(1)'}]}
        sources = search_web({**self.settings, 'search_url': 'http://localhost:8080'}, self.car['name'], 'oil?')
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['id'], 'W1')
        self.assertNotIn('PRIVATE', request.call_args.args[0])
        self.assertIn('2015+Honda+Civic', request.call_args.args[0])

    def test_prompt_uses_only_name_and_appearance(self):
        result = portrait_prompt(self.car['name'], 'blue coupe')
        self.assertIn('blue coupe', result)
        self.assertIn('2015 Honda Civic', result)
        self.assertNotIn('PRIVATE', result)

    def test_workflow_placeholder_replacement_preserves_json_and_original(self):
        template = {'1': {'class_type': 'CLIPTextEncode', 'inputs': {'text': '{{PROMPT}}'}}, '2': {'class_type': 'KSampler', 'inputs': {'seed': 42}}}
        workflow = prepare_workflow(template, 'blue "car"\nnew line')
        self.assertEqual(workflow['1']['inputs']['text'], 'blue "car"\nnew line')
        self.assertEqual(template['1']['inputs']['text'], '{{PROMPT}}')
        self.assertNotEqual(workflow['2']['inputs']['seed'], 42)
        with self.assertRaisesRegex(ValueError, 'API format'):
            prepare_workflow({'nodes': []}, 'car')
        with self.assertRaisesRegex(ValueError, 'PROMPT'):
            prepare_workflow({'1': {'class_type': 'Text', 'inputs': {'text': 'car'}}}, 'car')

    @patch('ai_garage.urlopen')
    @patch('ai_garage.request_json')
    def test_comfy_queue_history_download_and_persistence(self, request, urlopen):
        self.store.workflow_path().write_text(json.dumps({'1': {'class_type': 'Text', 'inputs': {'text': '{{PROMPT}}'}}}))
        request.side_effect = [{'prompt_id': 'job'}, {'job': {'outputs': {'9': {'images': [{'filename': 'car.png', 'type': 'output'}]}}}}]
        png = b'\x89PNG\r\n\x1a\nimage'
        urlopen.return_value.__enter__.return_value.read.return_value = png
        path = generate_portrait(self.store, self.settings, '../../civic', 'car')
        self.assertEqual(path.parent, self.store.directory)
        self.assertEqual(path.read_bytes(), png)
        self.assertEqual(json.loads(path.with_suffix('.json').read_text())['prompt'], 'car')

    @patch('ai_garage.request_json')
    def test_generation_errors_and_cancel_do_not_replace_portrait(self, request):
        self.store.workflow_path().write_text(json.dumps({'1': {'class_type': 'Text', 'inputs': {'text': '{{PROMPT}}'}}}))
        path = self.store.portrait_path('civic')
        path.write_bytes(b'old portrait')
        request.return_value = {'prompt_id': 'job'}
        with self.assertRaisesRegex(ValueError, 'Stopped waiting'):
            generate_portrait(self.store, self.settings, 'civic', 'car', cancelled=lambda: True)
        self.assertEqual(path.read_bytes(), b'old portrait')
        request.side_effect = [{'prompt_id': 'job'}, {'job': {'status': {'status_str': 'error'}}}]
        with self.assertRaisesRegex(ValueError, 'generation failed'):
            generate_portrait(self.store, self.settings, 'civic', 'car')
        self.assertEqual(path.read_bytes(), b'old portrait')

    @patch('ai_garage.request_json')
    def test_invalid_question_never_contacts_model(self, request):
        for question in ['', 'x' * 4001]:
            with self.assertRaises(ValueError):
                answer_question(self.store, self.settings, self.car, question)
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
