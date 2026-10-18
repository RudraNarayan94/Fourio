import os
import shutil
import numpy as np
from typing import List, Tuple, Optional

def DeleteFile(file_path: str) -> Optional[Exception]:
    # print(f"Deleting file: {file_path}")
    try:
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)
        return None
    except Exception as e:
        return e

def CreateFolder(folder_path: str) -> Optional[Exception]:
    try:
        #0o755 (octal) means: Owner gets full read/write/execute access
        os.makedirs(folder_path, mode=0o755, exist_ok=True)
        return None
    except Exception as e:
        return e

def MoveFile(source_path: str, destination_path: str) -> Optional[Exception]:
    try:
        if os.path.abspath(source_path) == os.path.abspath(destination_path):
            return None
        shutil.move(source_path, destination_path)
        return None
    except Exception as e:
        return e


def FloatsToBytes(data: List[float], bits_per_sample: int) -> Tuple[Optional[bytes], Optional[Exception]]:
    """
    Converts audio samples from normalized float64 [-1.0, 1.0] to 
    specified integer byte formats (Little Endian).
    """
    byte_data = bytearray()
    
    # numpy array for efficient conversion to avoid slow list iteration
    data_np = np.array(data, dtype=np.float64)

    try:
        if bits_per_sample == 8:
            # 8-bit unsigned PCM: [-1.0, 1.0] -> [0, 255]. Formula: val = (sample + 1.0) * 127.5
            # NumPy is used for vectorization:
            data_int = np.round((data_np + 1.0) * 127.5).astype(np.uint8)
            byte_data.extend(data_int.tobytes())
            
        elif bits_per_sample == 16:
            # 16-bit signed PCM: [-1.0, 1.0] -> [-32767, 32767]. Scale: 32767.0
            # struct.pack('<h' for short/16-bit, little-endian) is the fast equivalent to Go's binary.LittleEndian.PutUint16
            
            # The Go code uses int16(sample * 32767.0). NumPy handles this multiplication and type cast efficiently.
            data_int = np.clip(np.round(data_np * 32767.0), -32768, 32767).astype(np.int16)
            byte_data.extend(data_int.tobytes())

        elif bits_per_sample == 24:
            # 24-bit signed PCM: [-1.0, 1.0] -> [-8388607, 8388607]. Scale: 8388607.0 (2^23 - 1)
            # This case is complex as Python's standard 'struct' doesn't support 24-bit packing easily.
            # We translate the Go byte-by-byte construction:
            
            max_val = 8388607.0
            for sample in data_np:
                val = int(sample * max_val)
                # Equivalent to Go's PutUint32(buf, uint32(val)<<8) and taking buf[:3]
                # We need to extract the 3 bytes from the 32-bit integer:
                byte_data.append((val >> 0) & 0xFF)   # LSB
                byte_data.append((val >> 8) & 0xFF)
                byte_data.append((val >> 16) & 0xFF)  # MSB

        elif bits_per_sample == 32:
            # 32-bit signed PCM: [-1.0, 1.0] -> [-2147483647, 2147483647]. Scale: 2147483647.0
            # struct.pack('<i' for int/32-bit, little-endian)
            
            # Go uses int32(sample * 2147483647.0)
            data_int = np.clip(np.round(data_np * 2147483647.0), -2147483648, 2147483647).astype(np.int32)
            byte_data.extend(data_int.tobytes())

        else:
            return None, Exception(f"unsupported bitsPerSample: {bits_per_sample}")

        return bytes(byte_data), None

    except Exception as e:
        return None, e