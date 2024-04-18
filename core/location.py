from dataclasses import dataclass
import io
import re
import socket
import struct

from core import logger
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
            return struct.unpack("I", b[offset:offset + 4])[0]
        return 0

    def getInt2(self, b, offset):
        return ((b[offset] & 0x000000FF) | (b[offset+1] & 0x0000FF00))

    def close(self):
        if self.__f is not None:
            self.__f.close()
        self.vectorIndex = None
        self.contentBuff = None

@dataclass
class IPInfo:
    country: str = ""
    province: str = ""
    def __hash__(self):
        return hash(self.country.encode("utf-8") + self.province.encode("utf-8"))
    def __eq__(self, value: object) -> bool:
        return isinstance(value, IPInfo) and self.country == value.country and self.province == value.province
fixed_ip: dict[str, str] = {
    "104.166.": "美国|0|0|0|0"
}
country_iso = {
    "安道尔": "AD",
    "阿联酋": "AE",
    "阿富汗": "AF",
    "安提瓜和巴布达": "AG",
    "安圭拉": "AI",
    "阿尔巴尼亚": "AL",
    "亚美尼亚": "AM",
    "安哥拉": "AO",
    "南极洲": "AQ",
    "阿根廷": "AR",
    "美属萨摩亚": "AS",
    "奥地利": "AT",
    "澳大利亚": "AU",
    "阿鲁巴": "AW",
    "奥兰群岛": "AX",
    "阿塞拜疆": "AZ",
    "波黑": "BA",
    "巴巴多斯": "BB",
    "孟加拉": "BD",
    "比利时": "BE",
    "布基纳法索": "BF",
    "保加利亚": "BG",
    "巴林": "BH",
    "布隆迪": "BI",
    "贝宁": "BJ",
    "圣巴泰勒米": "BL",
    "百慕大": "BM",
    "文莱": "BN",
    "玻利维亚": "BO",
    "荷兰加勒比区": "BQ",
    "巴西": "BR",
    "巴哈马": "BS",
    "不丹": "BT",
    "布韦岛": "BV",
    "博茨瓦纳": "BW",
    "白俄罗斯": "BY",
    "伯利兹": "BZ",
    "加拿大": "CA",
    "科科斯群岛": "CC",
    "中非": "CF",
    "瑞士": "CH",
    "智利": "CL",
    "喀麦隆": "CM",
    "哥伦比亚": "CO",
    "哥斯达黎加": "CR",
    "古巴": "CU",
    "佛得角": "CV",
    "圣诞岛": "CX",
    "塞浦路斯": "CY",
    "捷克": "CZ",
    "德国": "DE",
    "吉布提": "DJ",
    "丹麦": "DK",
    "多米尼克": "DM",
    "多米尼加": "DO",
    "阿尔及利亚": "DZ",
    "厄瓜多尔": "EC",
    "爱沙尼亚": "EE",
    "埃及": "EG",
    "西撒哈拉": "EH",
    "厄立特里亚": "ER",
    "西班牙": "ES",
    "芬兰": "FI",
    "斐济群岛": "FJ",
    "斐济": "FJ",
    "福克兰": "FK",
    "福克兰群岛": "FK",
    "密克罗尼西亚": "FM",
    "法罗群岛": "FO",
    "法国": "FR",
    "法国南部领地": "FR",
    "加蓬": "GA",
    "格林纳达": "GD",
    "格鲁吉亚": "GE",
    "法属圭亚那": "GF",
    "加纳": "GH",
    "直布罗陀": "GI",
    "格陵兰": "GL",
    "几内亚": "GN",
    "瓜德罗普": "GP",
    "赤道几内亚": "GQ",
    "希腊": "GR",
    "南乔治亚岛和南桑威奇群岛": "GS",
    "危地马拉": "GT",
    "关岛": "GU",
    "几内亚比绍": "GW",
    "圭亚那": "GY",
    "赫德岛和麦克唐纳群岛": "HM",
    "洪都拉斯": "HN",
    "克罗地亚": "HR",
    "海地": "HT",
    "匈牙利": "HU",
    "印尼": "ID",
    "爱尔兰": "IE",
    "以色列": "IL",
    "马恩岛": "IM",
    "印度": "IN",
    "印度尼西亚": "IN",
    "英属印度洋领地": "IO",
    "伊拉克": "IQ",
    "伊朗": "IR",
    "冰岛": "IS",
    "意大利": "IT",
    "泽西岛": "JE",
    "牙买加": "JM",
    "约旦": "JO",
    "日本": "JP",
    "柬埔寨": "KH",
    "基里巴斯": "KI",
    "科摩罗": "KM",
    "科威特": "KW",
    "开曼群岛": "KY",
    "黎巴嫩": "LB",
    "列支敦士登": "LI",
    "斯里兰卡": "LK",
    "利比里亚": "LR",
    "莱索托": "LS",
    "立陶宛": "LT",
    "卢森堡": "LU",
    "拉脱维亚": "LV",
    "利比亚": "LY",
    "摩洛哥": "MA",
    "摩纳哥": "MC",
    "摩尔多瓦": "MD",
    "黑山": "ME",
    "圣马丁": "MF",
    "荷属圣马丁": "MF",
    "马达加斯加": "MG",
    "马绍尔群岛": "MH",
    "马其顿": "MK",
    "马里": "ML",
    "缅甸": "MM",
    "马提尼克": "MQ",
    "毛里塔尼亚": "MR",
    "蒙塞拉特岛": "MS",
    "马耳他": "MT",
    "马尔代夫": "MV",
    "马拉维": "MW",
    "墨西哥": "MX",
    "马来西亚": "MY",
    "纳米比亚": "NA",
    "尼日尔": "NE",
    "诺福克岛": "NF",
    "尼日利亚": "NG",
    "尼加拉瓜": "NI",
    "荷兰": "NL",
    "挪威": "NO",
    "尼泊尔": "NP",
    "瑙鲁": "NR",
    "阿曼": "OM",
    "巴拿马": "PA",
    "秘鲁": "PE",
    "法属波利尼西亚": "PF",
    "巴布亚新几内亚": "PG",
    "菲律宾": "PH",
    "巴基斯坦": "PK",
    "波兰": "PL",
    "皮特凯恩群岛": "PN",
    "波多黎各": "PR",
    "巴勒斯坦": "PS",
    "帕劳": "PW",
    "巴拉圭": "PY",
    "卡塔尔": "QA",
    "留尼旺": "RE",
    "罗马尼亚": "RO",
    "塞尔维亚": "RS",
    "俄罗斯": "RU",
    "卢旺达": "RW",
    "所罗门群岛": "SB",
    "塞舌尔": "SC",
    "苏丹": "SD",
    "瑞典": "SE",
    "新加坡": "SG",
    "斯洛文尼亚": "SI",
    "斯瓦尔巴群岛和 扬马延岛": "SJ",
    "斯洛伐克": "SK",
    "塞拉利昂": "SL",
    "圣马力诺": "SM",
    "塞内加尔": "SN",
    "索马里": "SO",
    "苏里南": "SR",
    "南苏丹": "SS",
    "圣多美和普林西比": "ST",
    "萨尔瓦多": "SV",
    "叙利亚": "SY",
    "斯威士兰": "SZ",
    "特克斯和凯科斯群岛": "TC",
    "乍得": "td",
    "多哥": "TG",
    "泰国": "TH",
    "托克劳": "TK",
    "托克劳群岛": "TK",
    "东帝汶": "TL",
    "突尼斯": "TN",
    "汤加": "TO",
    "土耳其": "TR",
    "图瓦卢": "TV",
    "坦桑尼亚": "TZ",
    "乌克兰": "UA",
    "乌干达": "UG",
    "美国": "US",
    "乌拉圭": "UY",
    "梵蒂冈": "VA",
    "委内瑞拉": "VE",
    "英属维尔京群岛": "VG",
    "美属维尔京群岛": "VI",
    "越南": "VN",
    "瓦利斯和富图纳": "WF",
    "瓦利斯和富图纳群岛": "WF",
    "萨摩亚": "WS",
    "也门": "YE",
    "马约特": "YT",
    "南非": "ZA",
    "赞比亚": "ZM",
    "津巴布韦": "ZW",
    "中国": "CN",
    "刚果布": "CG",
    "刚果金": "CD",
    "莫桑比克": "MZ",
    "根西岛": "GG",
    "冈比亚": "GM",
    "北马里亚纳群岛": "MP",
    "埃塞俄比亚": "ET",
    "新喀里多尼亚": "NC",
    "瓦努阿图": "VU",
    "法属南部领地": "TF",
    "纽埃": "NU",
    "美国本土外小岛屿": "UM",
    "库克群岛": "CK",
    "英国": "GB",
    "特立尼达和多巴哥": "TT",
    "圣文森特和格林纳丁斯": "VC",
    "新西兰": "NZ",
    "沙特阿拉伯": "SA",
    "老挝": "LA",
    "朝鲜": "KP",
    "韩国": "KR",
    "葡萄牙": "PT",
    "吉尔吉斯斯坦": "KG",
    "哈萨克斯坦": "KZ",
    "塔吉克斯坦": "TJ",
    "土库曼斯坦": "TM",
    "乌兹别克斯坦": "UZ",
    "圣基茨和尼维斯": "KN",
    "圣皮埃尔和密克隆": "PM",
    "圣皮埃尔和密克隆群岛": "PM",
    "圣赫勒拿": "SH",
    "圣卢西亚": "LC",
    "毛里求斯": "MU",
    "科特迪瓦": "CI",
    "肯尼亚": "KE",
    "蒙古": "MN"
}
cache: dict[str, IPInfo] = {}
empty: IPInfo = IPInfo()

ipaddress: XdbSearcher = XdbSearcher(contentBuff=XdbSearcher.loadContentFromFile("assets/ip.xdb"))
cn_level: str = r"(省|市|自治区|壮族自治区|回族自治区|维吾尔自治区|藏族自治区|蒙古族自治区|林区)"

def query(ip: str) -> IPInfo:
    if ip in cache:
        return cache[ip]
    data = ["" if data == "0" else data for data in fixed_ip.get(".".join(ip.split(".", 3)[0:2]) + ".", ipaddress.searchByIPStr(ip)).split("|")]
    country = country_iso.get(data[0], data[0])
    info = IPInfo(
        country, re.sub(cn_level, "", data[2]) if country == "CN" else ""
    )
    cache[ip] = info
    return info
