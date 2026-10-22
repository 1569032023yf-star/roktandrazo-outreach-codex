"""Bounded observation contract / 有界只读观测合同。"""
import unittest
from tools.city_channel_client import observation_body


class ObservationContractTests(unittest.TestCase):
    def test_fixed_empty_safe_never_refreshes(self):
        self.assertEqual(observation_body('safe'), {})

    def test_runtime_binding(self):
        self.assertEqual(observation_body('runtime', run_id='inventory:2026-10-22:bc1c588b', limit=50),
                         {'run_id': 'inventory:2026-10-22:bc1c588b', 'limit': 50})

    def test_city_and_provider(self):
        self.assertEqual(observation_body('city', city='Lake Placid'), {'city': 'Lake Placid'})
        self.assertEqual(observation_body('provider-audit', city='Cooperstown', hours=24),
                         {'city': 'Cooperstown', 'hours': 24})

    def test_injection_rejected(self):
        for value in ['../x', 'x; DROP TABLE leads', 'x\nNY', '', 'x' * 65, 22]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                observation_body('city', city=value)
        for value in ['../x', 'x y', 'x\n', '', 'x' * 81, 1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                observation_body('runtime', run_id=value)

    def test_ranges_and_boolean_rejected(self):
        for key, operation, values in [('hours', 'scheduler', [0, 169, True, '24']),
                                       ('limit', 'runtime', [0, 51, False, '1'])]:
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    observation_body(operation, **{key: value})

    def test_cross_operation_parameter_rejected(self):
        for operation, kwargs in [('safe', {'hours': 1}), ('city', {'run_id': 'x'}),
                                   ('apply', {'city': 'NY'}), ('telemetry', {'limit': 1})]:
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                observation_body(operation, **kwargs)


if __name__ == '__main__':
    unittest.main()
