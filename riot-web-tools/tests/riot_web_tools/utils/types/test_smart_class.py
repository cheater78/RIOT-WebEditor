from riot_web_tools.utils.types.smart_class import SmartClass

class MyTestSmartClass(SmartClass):
    def __init__(self,
                my_int: int = 1,
                my_str: str = "foo",
                my_bytes: bytes = b"hello world"):
        self.my_int = my_int
        self.my_str = my_str
        self.my_bytes = my_bytes


def test_eq():
    a: MyTestSmartClass = MyTestSmartClass()
    b: MyTestSmartClass = MyTestSmartClass()
    c: MyTestSmartClass = MyTestSmartClass(my_int=2)

    assert a == b
    assert a != c

def test_str():
    ref: str = "MyTestSmartClass(my_int=1, my_str=foo, my_bytes=hello world)"
    obj: MyTestSmartClass = MyTestSmartClass()
    obj_str: str = str(obj)

    assert obj_str == ref