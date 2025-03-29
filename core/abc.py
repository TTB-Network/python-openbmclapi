import abc
import enum
from pathlib import Path
from typing import Any
from cryptography import x509
from cryptography.x509 import oid


class BMCLAPIFile:
    def __init__(
        self,
        path: str,
        hash: str,
        size: int,
        mtime: float
    ):
        self.path = path
        self.hash = hash
        self.size = size
        self.mtime = mtime

    def __repr__(self):
        return f'BMCLAPIFile(path={self.path}, hash={self.hash}, size={self.size}, mtime={self.mtime})'
    
    def __hash__(self) -> int:
        return int(self.hash, 16)
    
    def __eq__(self, other: 'BMCLAPIFile'):
        return self.hash == other.hash
    
class OpenBMCLAPIConfiguration:
    def __init__(
        self,
        source: str,
        concurrency: int
    ):
        self.source = source
        self.concurrency = concurrency

class SocketEmitResult:
    def __init__(
        self,
        err: Any,
        ack: Any
    ):
        self.err = err
        self.ack = ack

    def __repr__(self):
        return f'SocketEmitResult(err={self.err}, ack={self.ack})'

class Certificate:
    def __init__(
        self,
        cert_type: 'CertificateType',
        cert: str,
        key: str
    ):
        self.cert_type = cert_type
        self.cert = cert
        self.key = key
        self.domains: list[str] = []

        crt = x509.load_pem_x509_certificate(
            Path(self.cert).read_bytes()
        )

        for attr in crt.subject.get_attributes_for_oid(oid.NameOID.COMMON_NAME):
            name = attr.value
            if not isinstance(name, str):
                continue
            self.domains.append(name)

    def __repr__(self) -> str:
        return f'Certificate(cert_type={self.cert_type}, cert={self.cert}, key={self.key}, domains={self.domains})'


class CertificateType(enum.Enum):
    PROXY = 'proxy'
    CLUSTER = 'cluster'
    BYOC = 'byoc'

class ResponseFile(metaclass=abc.ABCMeta):
    def __init__(
        self,
        size: int
    ):
        self.size = size

class ResponseFileLocal(ResponseFile):
    def __init__(
        self,
        path: Path,
        size: int
    ):
        super().__init__(size)
        self.path = path

    def __repr__(self) -> str:
        return f'ResponseFileLocal(path={self.path}, size={self.size})'
    
class ResponseFileRemote(ResponseFile):
    def __init__(
        self,
        url: str,
        size: int
    ):
        super().__init__(size)
        self.url = url

    def __repr__(self) -> str:
        return f'ResponseFileRemote(url={self.url}, size={self.size})'
    
class ResponseFileMemory(ResponseFile):
    def __init__(
        self,
        data: bytes,
        size: int
    ):
        super().__init__(size)
        self.data = data

    def __repr__(self) -> str:
        return f'ResponseFileMemory(data={self.data}, size={self.size})'
    
class ResponseFileNotFound(ResponseFile):
    def __init__(
        self,
    ):
        super().__init__(-1)

    def __repr__(self) -> str:
        return f'ResponseFileNotFound(size={self.size})'
