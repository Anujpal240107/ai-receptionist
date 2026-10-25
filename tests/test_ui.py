import os
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest

def button(at,label):
    return next(b for b in at.button if b.label==label)
def field(at,label):
    return next(f for f in at.text_input if f.label==label)

@unittest.skipUnless(os.environ.get("TEST_EMAIL"),"Requires ephemeral hosted integration accounts")
class RealStreamlit(unittest.TestCase):
    def signin(self):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"),default_timeout=30).run()
        self.assertFalse(at.exception)
        field(at,"Email").set_value(os.environ["TEST_EMAIL"])
        field(at,"Password").set_value(os.environ["TEST_PASSWORD"])
        button(at,"Sign in").click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertFalse(at.error,[e.value for e in at.error])
        return at

    def test_real_customer_order_persistence_and_signout(self):
        at=self.signin()
        button(at,"Start your first conversation").click().run(timeout=30)
        self.assertFalse(at.error,[e.value for e in at.error])
        field(at,"Customer name").set_value("UI Synthetic Customer")
        field(at,"Phone number").set_value("+91 99999 00000")
        at.text_area[0].set_value("Synthetic UI test delivery address only")
        next(n for n in at.number_input if n.key=="quantity-pizza").set_value(1)
        button(at,"Review order").click().run(timeout=30)
        self.assertFalse(at.error,[e.value for e in at.error])
        button(at,"Confirm and save order").click().run(timeout=30)
        self.assertFalse(at.error,[e.value for e in at.error])
        self.assertTrue(any("Order saved:" in s.value for s in at.success))
        self.assertTrue(any("200" in s.value for s in at.success))
        # A fresh Streamlit server session must fetch the same database-backed order.
        second=self.signin()
        self.assertFalse(second.error,[e.value for e in second.error])
        self.assertTrue(any("200" in e.label and "placed" in e.label for e in second.expander))
        button(second,"Sign out").click().run(timeout=30)
        self.assertFalse(second.exception)
        self.assertFalse(second.error,[e.value for e in second.error])
        self.assertIsNotNone(field(second,"Email"))

if __name__=="__main__":unittest.main()


