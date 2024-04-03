def split_bytes(data: bytes, key: bytes, count: int = 0):
    if count <= -1:
        count = 0
    else:
        count += 1
    data_length = len(data)
    key_length = len(key)
    splitted_data = []
    start = 0
    cur = 0
    for i in range(data_length):
        if data[i] == key[0] and i + key_length <= data_length:
            checked = True
            for j in range(1, key_length):
                if data[i + j] != key[j]:
                    checked = False
                    break
            if checked:
                splitted_data.append(data[start:i - 1])
                cur += 1
                start = i + key_length
        if count != 0 and cur >= count:
            break
    if count == 0 or cur < count:
        splitted_data.append(data[start:])
    return splitted_data



print(split_bytes(b"aa0aa00bb0bb00", b"00", 2))