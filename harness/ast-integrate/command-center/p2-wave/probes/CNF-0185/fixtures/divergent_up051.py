import abc


class Foo(abc.ABC):
    @abc.abstractclassmethod
    def class_method(cls):
        return 1
