from riot_web_tools.utils.types.smart_struct import *

class MyStructTag(StructTag):
    TypeA = 1
    TypeB = 2

@smartdataclass
class MyTaggedStruct(TaggedSmartStruct[MyStructTag]):
    pass

@smartdataclass
class MyStructA(MyTaggedStruct, tag=MyStructTag.TypeA):
    a: int = 1
    b: int = 1

@smartdataclass
class MyStructB(MyTaggedStruct, tag=MyStructTag.TypeB):
    a: int = 2
    b: str = "foo"

def test_tagged_smart_struct() -> None:
    domain_root_cls = MyTaggedStruct

    final_clss: dict[MyStructTag, type[MyTaggedStruct]] = {
        MyStructTag.TypeA: MyStructA,
        MyStructTag.TypeB: MyStructB
    }

    for tag, cls in final_clss.items():
        assert domain_root_cls.registry_get(tag) == cls