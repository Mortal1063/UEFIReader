import os
import re
import struct
import uuid
import gzip
import lzma
import argparse
from typing import List, Optional, Tuple
from pathlib import Path
from io import BytesIO
from datetime import datetime

class ByteOperations:
    @staticmethod
    def read_ascii_string(data: bytes, offset: int, length: int) -> str:
        return data[offset:offset+length].decode('ascii', errors='ignore')

    @staticmethod
    def read_unicode_string(data: bytes, offset: int, length: int) -> str:
        raw = data[offset:offset+length]
        return raw.decode('utf-16le', errors='ignore').rstrip('\x00').rstrip(' ')

    @staticmethod
    def write_ascii_string(data: bytearray, offset: int, text: str, max_len: Optional[int] = None):
        if max_len is not None:
            data[offset:offset+max_len] = b'\x00' * max_len
        b = text.encode('ascii')
        if max_len is not None and len(b) > max_len:
            b = b[:max_len]
        data[offset:offset+len(b)] = b

    @staticmethod
    def write_unicode_string(data: bytearray, offset: int, text: str, max_len: Optional[int] = None):
        if max_len is not None:
            data[offset:offset+max_len] = b'\x00' * max_len
        b = text.encode('utf-16le')
        if max_len is not None and len(b) > max_len:
            b = b[:max_len]
        data[offset:offset+len(b)] = b

    @staticmethod
    def read_uint32(data: bytes, offset: int) -> int:
        return struct.unpack_from('<I', data, offset)[0]

    @staticmethod
    def write_uint32(data: bytearray, offset: int, value: int):
        struct.pack_into('<I', data, offset, value)

    @staticmethod
    def read_int32(data: bytes, offset: int) -> int:
        return struct.unpack_from('<i', data, offset)[0]

    @staticmethod
    def write_int32(data: bytearray, offset: int, value: int):
        struct.pack_into('<i', data, offset, value)

    @staticmethod
    def read_uint16(data: bytes, offset: int) -> int:
        return struct.unpack_from('<H', data, offset)[0]

    @staticmethod
    def write_uint16(data: bytearray, offset: int, value: int):
        struct.pack_into('<H', data, offset, value)

    @staticmethod
    def read_int16(data: bytes, offset: int) -> int:
        return struct.unpack_from('<h', data, offset)[0]

    @staticmethod
    def write_int16(data: bytearray, offset: int, value: int):
        struct.pack_into('<h', data, offset, value)

    @staticmethod
    def read_uint8(data: bytes, offset: int) -> int:
        return data[offset]

    @staticmethod
    def write_uint8(data: bytearray, offset: int, value: int):
        data[offset] = value & 0xFF

    @staticmethod
    def read_uint24(data: bytes, offset: int) -> int:
        return data[offset] | (data[offset+1] << 8) | (data[offset+2] << 16)

    @staticmethod
    def write_uint24(data: bytearray, offset: int, value: int):
        data[offset] = value & 0xFF
        data[offset+1] = (value >> 8) & 0xFF
        data[offset+2] = (value >> 16) & 0xFF

    @staticmethod
    def read_uint64(data: bytes, offset: int) -> int:
        return struct.unpack_from('<Q', data, offset)[0]

    @staticmethod
    def write_uint64(data: bytearray, offset: int, value: int):
        struct.pack_into('<Q', data, offset, value)

    @staticmethod
    def read_guid(data: bytes, offset: int) -> uuid.UUID:
        b = data[offset:offset+16]
        return uuid.UUID(bytes_le=b)

    @staticmethod
    def write_guid(data: bytearray, offset: int, guid: uuid.UUID):
        data[offset:offset+16] = guid.bytes_le

    @staticmethod
    def align(base: int, offset: int, alignment: int) -> int:
        rem = (offset - base) % alignment
        if rem == 0:
            return offset
        return offset + (alignment - rem)

    @staticmethod
    def calculate_checksum8(data: bytes, offset: int, size: int) -> int:
        s = sum(data[offset:offset+size]) & 0xFF
        return (0x100 - s) & 0xFF

    @staticmethod
    def calculate_checksum16(data: bytes, offset: int, size: int) -> int:
        s = 0
        for i in range(offset, offset+size-1, 2):
            s += struct.unpack_from('<H', data, i)[0]
        return (0x10000 - (s & 0xFFFF)) & 0xFFFF

    @staticmethod
    def crc32(data: bytes, offset: int, size: int) -> int:
        crc = 0xFFFFFFFF
        for i in range(offset, offset+size):
            crc ^= data[i]
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1
        return crc ^ 0xFFFFFFFF

    @staticmethod
    def find_pattern(data: bytes, pattern: bytes, mask: Optional[bytes] = None,
                     start: int = 0, size: Optional[int] = None) -> Optional[int]:
        if size is None:
            size = len(data) - start
        end = start + size - len(pattern) + 1
        for i in range(start, end):
            match = True
            for j, p in enumerate(pattern):
                if mask is not None and mask[j] != 0:
                    continue
                if data[i+j] != p:
                    match = False
                    break
            if match:
                return i
        return None

    @staticmethod
    def find_ascii(data: bytes, text: str) -> Optional[int]:
        return ByteOperations.find_pattern(data, text.encode('ascii'))

    @staticmethod
    def find_unicode(data: bytes, text: str) -> Optional[int]:
        pat = text.encode('utf-16le')
        return ByteOperations.find_pattern(data, pat)

    @staticmethod
    def find_uint32(data: bytes, value: int) -> Optional[int]:
        return ByteOperations.find_pattern(data, struct.pack('<I', value))

class Converter:
    @staticmethod
    def convert_hex_to_string(data: bytes, sep: str = " ") -> str:
        return sep.join(f"{b:02X}" for b in data)

    @staticmethod
    def convert_string_to_hex(s: str) -> bytes:
        s = s.replace(" ", "").replace("-", "")
        if len(s) % 2 != 0:
            raise ValueError("Hex string must have even length")
        return bytes.fromhex(s)

class GZip:
    @staticmethod
    def decompress(data: bytes, offset: int, size: int) -> bytes:
        with gzip.GzipFile(fileobj=BytesIO(data[offset:offset+size])) as f:
            return f.read()

class LZMA:
    @staticmethod
    def decompress(data: bytes, offset: int, size: int) -> bytes:
        chunk = data[offset:offset+size]
        return lzma.decompress(chunk)

class EFISection:
    def __init__(self, type_: str, data: bytes, name: str = ""):
        self.type = type_
        self.data = data
        self.name = name

class EFI:
    def __init__(self, guid: uuid.UUID, type_: str, sections: List[EFISection]):
        self.guid = guid
        self.type = type_
        self.sections = sections

class UEFI:
    def __init__(self, binary: bytes):
        self.binary = binary
        self.efis: List[EFI] = []
        self.load_priority: set = set()
        self.build_id = ""

        offset = ByteOperations.find_ascii(binary, "_FVH")
        if offset is None:
            raise ValueError("_FVH marker not found")
        volume_header_offset = offset - 0x28
        self.efis.extend(self.handle_volume_image(binary, volume_header_offset))

        build_ids = self.try_get_build_path(binary)
        if build_ids:
            self.build_id = build_ids[0]

    def extract_uefi(self, output_dir: str):
        self.extract_dxes(output_dir)
        self.extract_apriori(output_dir)

    def try_get_file_path(self, data: bytes) -> List[str]:
        text = data.decode('ascii', errors='ignore')
        pattern = re.compile(rb'[a-zA-Z/\\0-9_\-.]+\.dll\b')
        matches = pattern.findall(text.encode('ascii'))
        results = [m.decode('ascii') for m in matches]
        normalized = [self.normalize_build_path(s) for s in results]
        return [s for s in normalized if s.count('/') > 1]

    def try_get_build_path(self, data: bytes) -> List[str]:
        text = data.decode('ascii', errors='ignore')
        pattern = re.compile(rb'QC_IMAGE_VERSION_STRING=[a-zA-Z/\\0-9_\-.]+')
        matches = pattern.findall(text.encode('ascii'))
        results = [m.decode('ascii').replace('QC_IMAGE_VERSION_STRING=', '') for m in matches]
        return results

    def normalize_build_path(self, path: str) -> str:
        path = path.replace('\\', '/')
        if 'ARM/' in path:
            return path.split('ARM/')[-1]
        elif 'AARCH64/' in path:
            return path.split('AARCH64/')[-1]
        else:
            return path

    def handle_volume_image(self, data: bytes, offset: int) -> List[EFI]:
        if ByteOperations.read_ascii_string(data, offset + 0x28, 4) != "_FVH":
            raise ValueError("Invalid FVH magic")
        if not self.verify_volume_checksum(data, offset):
            raise ValueError("Volume checksum failed")

        volume_header_size = ByteOperations.read_uint16(data, offset + 0x30)
        file_offset = offset + volume_header_size
        volume_data = data[file_offset:]
        return self.handle_file_loop(volume_data, 0, 0)

    def handle_file_loop(self, data: bytes, offset: int, base: int) -> List[EFI]:
        efis: List[EFI] = []
        while offset < len(data):
            if offset + 0x18 > len(data):
                break
            file_type, file_size, file_header_size, file_guid = self.read_file_metadata(data, offset)
            if file_size == 0 or offset + file_size > len(data):
                break
            if file_type == 0x01:
                raw_data = data[offset+file_header_size:offset+file_size]
                section = EFISection("RAW", raw_data, name=str(file_guid))
                efis.append(EFI(file_guid, "RAW", [section]))
            elif file_type == 0x02:
                if file_guid == uuid.UUID("FC510EE7-FFDC-11D4-BD41-0080C73C8881"):
                    raw_data = data[offset+file_header_size:offset+file_size]
                    sections = self.handle_section_loop(raw_data, 0, offset+file_header_size)
                    if sections and sections[0].type == "RAW":
                        for i in range(0, len(sections[0].data), 16):
                            guid = ByteOperations.read_guid(sections[0].data, i)
                            self.load_priority.add(guid)
                else:
                    raw_data = data[offset+file_header_size:offset+file_size]
                    sections = self.handle_section_loop(raw_data, 0, offset+file_header_size)
                    efis.append(EFI(file_guid, "FREEFORM", sections))
            elif file_type == 0x03:
                raw_data = data[offset+file_header_size:offset+file_size]
                sections = self.handle_section_loop(raw_data, 0, offset+file_header_size)
                efis.append(EFI(file_guid, "SECURITY_CORE", sections))
            elif file_type == 0x05:
                raw_data = data[offset+file_header_size:offset+file_size]
                sections = self.handle_section_loop(raw_data, 0, offset+file_header_size)
                efis.append(EFI(file_guid, "DXE_CORE", sections))
            elif file_type == 0x07:
                raw_data = data[offset+file_header_size:offset+file_size]
                sections = self.handle_section_loop(raw_data, 0, offset+file_header_size)
                efis.append(EFI(file_guid, "DRIVER", sections))
            elif file_type == 0x09:
                raw_data = data[offset+file_header_size:offset+file_size]
                sections = self.handle_section_loop(raw_data, 0, offset+file_header_size)
                efis.append(EFI(file_guid, "APPLICATION", sections))
            elif file_type == 0x0B:
                raw_data = data[offset+file_header_size:offset+file_size]
                sections = self.handle_section_loop(raw_data, 0, offset+file_header_size)
                for sec in sections:
                    if sec.type == "FV":
                        efis.extend(self.handle_volume_image(sec.data, 0))
            elif file_type == 0xF0:
                pass
            elif file_type in (0x00, 0xFF):
                break
            else:
                raise ValueError(f"Unsupported file type 0x{file_type:X}")
            offset += file_size
            offset = ByteOperations.align(base, offset, 8)
        return efis

    def read_file_metadata(self, data: bytes, offset: int) -> Tuple[int, int, int, uuid.UUID]:
        guid_bytes = data[offset:offset+16]
        guid = uuid.UUID(bytes_le=guid_bytes)
        file_type = data[offset+0x12]
        attributes = data[offset+0x13]
        file_size = ByteOperations.read_uint24(data, offset+0x14)
        file_header_size = 0x18
        if attributes == 0x41:
            file_size = ByteOperations.read_uint64(data, offset+0x18)
            file_header_size = 0x20
        return file_type, file_size, file_header_size, guid

    def read_section_metadata(self, data: bytes, offset: int) -> Tuple[int, int]:
        section_size = ByteOperations.read_uint24(data, offset)
        section_type = data[offset+3]
        return section_size, section_type

    def handle_section_loop(self, data: bytes, offset: int, base: int) -> List[EFISection]:
        sections: List[EFISection] = []
        while offset < len(data):
            if offset + 4 > len(data):
                break
            section_size, section_type = self.read_section_metadata(data, offset)
            if section_size == 0 or offset + section_size > len(data):
                break
            if section_type == 0x02:
                subsections = self.parse_guid_defined_section(data, offset, base)
                sections.extend(subsections)
            elif section_type == 0x10:
                raw = data[offset+4:offset+section_size]
                sections.append(EFISection("PE32", raw))
            elif section_type == 0x11:
                raw = data[offset+4:offset+section_size]
                sections.append(EFISection("PIC", raw))
            elif section_type == 0x12:
                raw = data[offset+4:offset+section_size]
                sections.append(EFISection("TE", raw))
            elif section_type == 0x13:
                raw = data[offset+4:offset+section_size]
                sections.append(EFISection("DXE_DEPEX", raw))
            elif section_type == 0x14:
                pass
            elif section_type == 0x15:
                name = ByteOperations.read_unicode_string(data, offset+4, section_size-4)
                name = name.rstrip('\x00').rstrip(' ')
                raw = data[offset+4:offset+section_size]
                sections.append(EFISection("UI", raw, name))
            elif section_type == 0x17:
                raw = data[offset+4:offset+section_size]
                sections.append(EFISection("FV", raw))
            elif section_type == 0x18:
                raw = data[offset+4:offset+section_size]
                sections.append(EFISection("RAW", raw))
            elif section_type == 0x19:
                raw = data[offset+4:offset+section_size]
                sections.append(EFISection("RAW", raw))
            elif section_type == 0x1B:
                raw = data[offset+4:offset+section_size]
                sections.append(EFISection("PEI_DEPEX", raw))
            elif section_type in (0x00, 0xFF):
                break
            else:
                raise ValueError(f"Unsupported section type 0x{section_type:X}")
            offset += section_size
            offset = ByteOperations.align(base, offset, 4)
        return sections

    def parse_guid_defined_section(self, data: bytes, offset: int, base: int) -> List[EFISection]:
        section_size, section_type = self.read_section_metadata(data, offset)
        if section_type != 0x02:
            raise ValueError("Not a GUID_DEFINED section")
        guid_bytes = data[offset+4:offset+20]
        guid = uuid.UUID(bytes_le=guid_bytes)
        section_header_size = ByteOperations.read_uint16(data, offset+0x14)
        compressed_offset = offset + section_header_size
        compressed_size = section_size - section_header_size

        decompressed_data: Optional[bytes] = None
        if guid == uuid.UUID("EE4E5898-3914-4259-9D6E-DC7BD79403CF") or \
           guid == uuid.UUID("bd9921ea-ed91-404a-8b2f-b4d724747c8c"):
            decompressed_data = LZMA.decompress(data, compressed_offset, compressed_size)
        elif guid == uuid.UUID("1D301FE9-BE79-4353-91C2-D23BC959AE0C"):
            decompressed_data = GZip.decompress(data, compressed_offset, compressed_size)
        else:
            raise ValueError(f"Unsupported compression GUID: {guid}")

        return self.handle_section_loop(decompressed_data, 0, base)

    def verify_volume_checksum(self, data: bytes, offset: int) -> bool:
        volume_header_size = ByteOperations.read_uint16(data, offset+0x30)
        header = bytearray(data[offset:offset+volume_header_size])
        ByteOperations.write_uint16(header, 0x32, 0)
        current = ByteOperations.read_uint16(data, offset+0x32)
        calculated = ByteOperations.calculate_checksum16(bytes(header), 0, volume_header_size)
        return current == calculated

    def extract_dxes(self, output_dir: str):
        dxe_load_list: List[str] = []
        dxe_include_list: List[str] = []

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for efi in self.efis:
            has_path = any(self.is_section_with_path(s) for s in efi.sections)
            has_ui = any(self.is_section_with_ui(s) for s in efi.sections)

            if has_path:
                sections_with_path = [s for s in efi.sections if self.is_section_with_path(s)]
                all_paths = []
                for sec in sections_with_path:
                    all_paths.extend(self.try_get_file_path(sec.data))

                ui_sections = [s for s in efi.sections if self.is_section_with_ui(s)]

                if all_paths:
                    parts = all_paths[0].split('/')
                    if len(parts) >= 3:
                        output_subdir = '/'.join(parts[:-3])
                        module_name = parts[-3]
                    else:
                        output_subdir = ""
                        module_name = all_paths[0].replace('/', '_')
                    if len(ui_sections) == 1:
                        base_name = ui_sections[0].name
                    else:
                        base_name = module_name
                else:
                    if len(ui_sections) == 1:
                        base_name = ui_sections[0].name
                        module_name = base_name.replace(' ', '_')
                        output_subdir = base_name.replace(' ', '_')
                    else:
                        continue

                module_type = efi.type.upper()
                if efi.type == "APPLICATION":
                    module_type = "UEFI_APPLICATION"
                elif efi.type == "DRIVER":
                    module_type = "DXE_DRIVER"
                elif efi.type == "SECURITY_CORE":
                    module_type = "SEC"

                has_depex = any(s.type == "DXE_DEPEX" for s in efi.sections)

                inf_lines = [
                    "# ****************************************************************************",
                    "# AUTOGENERATED BY UEFIReader",
                    f"# AUTOGENED AS {module_name}.inf",
                    "# DO NOT MODIFY",
                    f"# GENERATED ON: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
                    "",
                    "[Defines]",
                    "  INF_VERSION    = 0x0001001B",
                    f"  BASE_NAME      = {base_name}",
                    f"  FILE_GUID      = {str(efi.guid).upper()}",
                    f"  MODULE_TYPE    = {module_type}",
                    "  VERSION_STRING = 1.0",
                    ("  ENTRY_POINT    = EfiEntry" if has_depex else ""),
                    "",
                    "[Binaries.AARCH64]"
                ]

                for sec in efi.sections:
                    if sec.type == "UI":
                        continue
                    ext = sec.type.lower()
                    if sec.type == "PE32":
                        ext = "efi"
                    elif sec.type == "DXE_DEPEX":
                        ext = "depex"
                    out_file = f"{module_name}.{ext}"
                    inf_lines.append(f"   {sec.type}|{out_file}|*")
                    full_out = output_path / output_subdir.replace('/', os.sep) / out_file
                    full_out.parent.mkdir(parents=True, exist_ok=True)
                    full_out.write_bytes(sec.data)

                inf_lines.append("")
                if has_depex:
                    inf_lines.append("[Depex]")
                    inf_lines.append("  TRUE")
                inf_lines.append("# AUTOGEN ENDS")
                inf_lines.append("# ****************************************************************************")
                inf_content = "\n".join(inf_lines)

                inf_file = output_path / output_subdir.replace('/', os.sep) / f"{module_name}.inf"
                inf_file.parent.mkdir(parents=True, exist_ok=True)
                inf_file.write_text(inf_content)

                rel_path = (output_subdir + "/" + module_name + ".inf").replace('\\', '/')
                dxe_load_list.append(f"INF {rel_path}")
                dxe_include_list.append(rel_path)

            elif has_ui:
                ui_sections = [s for s in efi.sections if self.is_section_with_ui(s)]
                if len(ui_sections) != 1:
                    continue
                file_name = ui_sections[0].name
                dxe_load_list.append("")
                dxe_load_list.append(f"FILE FREEFORM = {str(efi.guid).upper()} {{")
                for sec in efi.sections:
                    if sec.type == "RAW":
                        raw_dir = output_path / "RawFiles"
                        real_name = file_name.replace(' ', '_').replace('\\', '/')
                        dst = raw_dir / real_name
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(sec.data)
                        dxe_load_list.append(f"    SECTION {sec.type} = RawFiles/{real_name}")
                    elif sec.type == "UI":
                        dxe_load_list.append(f"    SECTION {sec.type} = \"{sec.name}\"")
                dxe_load_list.append("}")
                dxe_load_list.append("")
            else:
                for sec in efi.sections:
                    if sec.type == "RAW":
                        raw_dir = output_path / "RawFiles"
                        dst = raw_dir / str(efi.guid).replace('-', '')
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(sec.data)

        (output_path / "DXE.dsc.inc").write_text("\n".join(dxe_include_list))
        (output_path / "DXE.inc").write_text("\n".join(dxe_load_list))

    def extract_apriori(self, output_dir: str):
        apriori_lines = ["APRIORI DXE {"]
        for efi in self.efis:
            if not any(self.is_section_with_path(s) for s in efi.sections):
                continue
            sections_with_path = [s for s in efi.sections if self.is_section_with_path(s)]
            all_paths = []
            for sec in sections_with_path:
                all_paths.extend(self.try_get_file_path(sec.data))
            ui_sections = [s for s in efi.sections if self.is_section_with_ui(s)]

            if all_paths:
                parts = all_paths[0].split('/')
                if len(parts) >= 3:
                    output_subdir = '/'.join(parts[:-3])
                    module_name = parts[-3]
                else:
                    output_subdir = ""
                    module_name = all_paths[0].replace('/', '_')
            else:
                if ui_sections:
                    base_name = ui_sections[0].name
                    module_name = base_name.replace(' ', '_')
                    output_subdir = base_name.replace(' ', '_')
                else:
                    continue

            if efi.guid in self.load_priority:
                rel_path = (output_subdir + "/" + module_name + ".inf").replace('\\', '/')
                apriori_lines.append(f"    INF {rel_path}")
        apriori_lines.append("}")
        (Path(output_dir) / "APRIORI.inc").write_text("\n".join(apriori_lines))

    def is_section_with_path(self, sec: EFISection) -> bool:
        return sec.type not in ("UI", "DXE_DEPEX", "RAW", "PEI_DEPEX")

    def is_section_with_ui(self, sec: EFISection) -> bool:
        return sec.type == "UI"

def main():
    parser = argparse.ArgumentParser(description="UEFIReader - extract DXEs and generate INF files")
    parser.add_argument("uefi_image", help="Path to UEFI image / XBL image")
    parser.add_argument("output_dir", help="Output directory")
    args = parser.parse_args()

    if not os.path.isfile(args.uefi_image):
        print(f"Error: {args.uefi_image} not found")
        return

    with open(args.uefi_image, "rb") as f:
        data = f.read()

    try:
        uefi = UEFI(data)
        if uefi.build_id:
            output_dir = os.path.join(args.output_dir, uefi.build_id)
        else:
            output_dir = args.output_dir
        uefi.extract_uefi(output_dir)
        print(f"Extraction complete. Output in {output_dir}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()