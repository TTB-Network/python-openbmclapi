import abc

class BaseSync(
    metaclass=abc.ABCMeta
):
    @abc.abstractmethod
    def __init__(
        self,
        *args,
        **kwargs
    ):
        ...

    @abc.abstractmethod
    async def sync(self):
        raise NotImplementedError