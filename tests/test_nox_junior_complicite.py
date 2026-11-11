import unittest
from cogs import nox_junior_complicite as c

class CompliciteTests(unittest.TestCase):
    def test_four_activities_replayable(self):
        for name in c.ACTIVITIES:
            for _ in range(2):
                state = c.start(name)
                self.assertFalse(state['done'])
                for _ in range(3):
                    self.assertTrue(c.choices(state))
                    state = c.advance(state, 0)
                self.assertTrue(state['done'])
                self.assertEqual(c.choices(state), ())
                with self.assertRaises(ValueError): c.advance(state, 0)

    def test_invalid_choices(self):
        with self.assertRaises(ValueError): c.start('invalid')
        state = c.start('parler')
        for choice in (-1, 99, '0'):
            with self.assertRaises(ValueError): c.advance(state, choice)

if __name__ == '__main__': unittest.main()
