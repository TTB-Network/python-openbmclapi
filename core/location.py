import io
import socket
import struct

from core.const import (
    XDB_HeaderInfoLength as HeaderInfoLength,
    XDB_VectorIndexRows as VectorIndexRows,
    XDB_VectorIndexCols as VectorIndexCols,
    XDB_VectorIndexSize as VectorIndexSize,
    XDB_SegmentIndexSize as SegmentIndexSize,
)


class XdbSearcher(object):
    __f = None

    # the minimal memory allocation.
    vectorIndex = None
    # 整个读取xdb，保存在内存中
    contentBuff = None

    cache: dict[str, str] = {}

    @staticmethod
    def loadVectorIndexFromFile(dbfile):
        f = io.open(dbfile, "rb")
        f.seek(HeaderInfoLength)
        vi_len = VectorIndexRows * VectorIndexCols * SegmentIndexSize
        vector_data = f.read(vi_len)
        f.close()
        return vector_data

    @staticmethod
    def loadContentFromFile(dbfile):
        f = io.open(dbfile, "rb")
        all_data = f.read()
        f.close()
        return all_data

    def __init__(self, dbfile=None, vectorIndex=None, contentBuff=None):
        self.initDatabase(dbfile, vectorIndex, contentBuff)

    def search(self, ip):
        if isinstance(ip, str):
            if not ip.isdigit(): ip = self.ip2long(ip)
            return self.searchByIPLong(ip)
        else:
            return self.searchByIPLong(ip)

    def searchByIPStr(self, ip):
        if not ip.isdigit(): ip = self.ip2long(ip)
        if ip in self.cache:
            return self.cache[ip]
        self.cache[ip] = self.searchByIPLong(ip)
        return self.cache[ip]

    def searchByIPLong(self, ip):
        # locate the segment index block based on the vector index
        sPtr = ePtr = 0
        il0 = (int)((ip >> 24) & 0xFF)
        il1 = (int)((ip >> 16) & 0xFF)
        idx = il0 * VectorIndexCols * VectorIndexSize + il1 * VectorIndexSize

        if self.vectorIndex is not None:
            sPtr = self.getLong(self.vectorIndex, idx)
            ePtr = self.getLong(self.vectorIndex, idx + 4)
        elif self.contentBuff is not None:
            sPtr = self.getLong(self.contentBuff, HeaderInfoLength + idx)
            ePtr = self.getLong(self.contentBuff, HeaderInfoLength + idx + 4)
        else:
            self.__f.seek(HeaderInfoLength + idx) # type: ignore
            buffer_ptr = self.__f.read(8) # type: ignore
            sPtr = self.getLong(buffer_ptr, 0)
            ePtr = self.getLong(buffer_ptr, 4)

        # binary search the segment index block to get the region info
        dataLen = dataPtr = int(-1)
        l = int(0)
        h = int((ePtr - sPtr) / SegmentIndexSize)
        while l <= h:
            m = int((l + h) >> 1)
            p = int(sPtr + m * SegmentIndexSize)
            # read the segment index
            buffer_sip = self.readBuffer(p, SegmentIndexSize)
            sip = self.getLong(buffer_sip, 0)
            if ip < sip:
                h = m - 1
            else:
                eip = self.getLong(buffer_sip, 4)
                if ip > eip:
                    l = m + 1
                else:
                    dataLen = self.getInt2(buffer_sip, 8)
                    dataPtr = self.getLong(buffer_sip, 10)
                    break

        # empty match interception
        if dataPtr < 0:
            return ""

        buffer_string = self.readBuffer(dataPtr, dataLen)
        return_string = buffer_string.decode("utf-8") # type: ignore
        return return_string

    def readBuffer(self, offset, length):
        buffer = None
        # check the in-memory buffer first
        if self.contentBuff is not None:
            buffer = self.contentBuff[offset:offset + length]
            return buffer

        # read from the file handle
        if self.__f is not None:
            self.__f.seek(offset)
            buffer = self.__f.read(length)
        return buffer

    def initDatabase(self, dbfile, vi, cb):
        """
        " initialize the database for search
        " param: dbFile, vectorIndex, contentBuff
        """
        if cb is not None:
            self.__f = None
            self.vectorIndex = None
            self.contentBuff = cb
        else:
            self.__f = io.open(dbfile, "rb")
            self.vectorIndex = vi

    def ip2long(self, ip):
        _ip = socket.inet_aton(ip)
        return struct.unpack("!L", _ip)[0]

    def isip(self, ip):
        p = ip.split(".")

        if len(p) != 4: return False
        for pp in p:
            if not pp.isdigit(): return False
            if len(pp) > 3: return False
            if int(pp) > 255: return False
        return True

    def getLong(self, b, offset):
        if len(b[offset:offset + 4]) == 4:
            return struct.unpack('I', b[offset:offset + 4])[0]
        return 0

    def getInt2(self, b, offset):
        return ((b[offset] & 0x000000FF) | (b[offset+1] & 0x0000FF00))

    def close(self):
        if self.__f is not None:
            self.__f.close()
        self.vectorIndex = None
        self.contentBuff = None

ipaddress: XdbSearcher =  XdbSearcher(contentBuff=XdbSearcher.loadContentFromFile('data/ip.xdb'))