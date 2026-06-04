import struct
import os
import urllib.request

# 运营商映射表
ISP_MAP = {
    1: "移动", 2: "联通", 3: "电信",
    4: "电信虚拟运营商", 5: "联通虚拟运营商", 6: "移动虚拟运营商",
    7: "中国广电", 8: "中国广电虚拟运营商"
}

# GitHub 原始文件直连下载地址
ONLINE_DAT_URL = "https://raw.githubusercontent.com/pangongzi/phone/master/src/data/phone.dat"

class PhoneDataGuesser:
    def __init__(self, dat_path="phone.dat"):
        self.dat_path = dat_path
        self.records = []
        self.file_content = None
        
        # 核心逻辑：先尝试在线获取并保存到本地，失败则直接读取本地
        if self._fetch_and_save_data():
            self._load_dat()
        else:
            print("❌ 错误: 无法加载任何数据（在线下载失败且本地文件不存在/损坏）。")

    def _fetch_and_save_data(self):
        """尝试在线下载最新数据，成功则保存到本地；失败则退回读取本地文件"""
        print("🔄 正在尝试从 GitHub 获取最新的 phone.dat 文件...")
        try:
            with urllib.request.urlopen(ONLINE_DAT_URL, timeout=5) as response:
                self.file_content = response.read()
            
            # 在线获取成功后，立即保存/更新到本地 phone.dat
            try:
                with open(self.dat_path, "wb") as f:
                    f.write(self.file_content)
                print(f"✅ 成功：已在线获取最新数据，并自动保存到本地 [{self.dat_path}] ！")
            except Exception as save_err:
                print(f"⚠️ 提示：在线数据获取成功，但在保存到本地时失败 ({save_err})")
                
            return True
            
        except Exception as e:
            print(f"⚠️ 提示：在线获取失败 ({e})。正在尝试读取本地历史文件...")
            
            # 在线失败，检查并读取本地文件
            if os.path.exists(self.dat_path):
                try:
                    with open(self.dat_path, "rb") as f:
                        self.file_content = f.read()
                    print(f"💾 成功：已加载本地历史文件 [{self.dat_path}]")
                    return True
                except Exception as local_err:
                    print(f"❌ 错误：读取本地文件失败 -> {local_err}")
                    return False
            else:
                print(f"❌ 错误：本地未找到 [{self.dat_path}] 文件。")
                return False

    def _load_dat(self):
        """解析二进制数据结构"""
        content = self.file_content
        if len(content) < 8:
            return
            
        first_index_offset = struct.unpack("<I", content[4:8])[0]
        index_block = content[first_index_offset:]
        record_length = 9
        total_records = len(index_block) // record_length
        
        for i in range(total_records):
            start = i * record_length
            item = index_block[start: start + record_length]
            if len(item) < record_length:
                break
                
            pref_7, detail_offset, isp_type = struct.unpack("<IIB", item)
            end_offset = content.find(b'\x00', detail_offset)
            detail_str = content[detail_offset:end_offset].decode("utf-8")
            
            parts = detail_str.split("|")
            province = parts[0] if len(parts) > 0 else ""
            city = parts[1] if len(parts) > 1 else ""
            
            self.records.append({
                "pref_7": str(pref_7),
                "province": province,
                "city": city
            })

    def guess_and_save(self, prefix_3, suffix_4, location_keyword, output_txt="resultPHONE.txt", output_vcf="resultPHONE.vcf"):
        """根据条件推测中间四位，并生成 TXT 文件与 VCF 通讯录文件"""
        if not self.records:
            return

        prefix_3 = str(prefix_3).strip()
        suffix_4 = str(suffix_4).strip()
        location_keyword = str(location_keyword).strip()
        
        phone_list = []

        for rec in self.records:
            if not rec["pref_7"].startswith(prefix_3):
                continue
            if location_keyword not in rec["province"] and location_keyword not in rec["city"]:
                continue
            
            middle_4 = rec["pref_7"][3:]
            full_phone = f"{prefix_3}{middle_4}{suffix_4}"
            phone_list.append((full_phone, rec["province"], rec["city"]))
            
        if phone_list:
            # 1. 写入 TXT 文件（纯号码）
            with open(output_txt, "w", encoding="utf-8") as f_txt:
                for phone, _, _ in phone_list:
                    f_txt.write(f"{phone}\n")
            print(f"🎉 成功！已将找到的 {len(phone_list)} 个手机号保存到本地文本: {output_txt}")

            # 2. 【新增】写入 VCF 格式文件（标准通讯录格式）
            with open(output_vcf, "w", encoding="utf-8") as f_vcf:
                for idx, (phone, prov, city) in enumerate(phone_list, start=1):
                    # 联系人姓名格式：归属地_前缀_后缀_序号 (例如: 杭州_139_8888_001)
                    contact_name = f"{city or prov}_{prefix_3}_{suffix_4}_{idx:03d}"
                    
                    f_vcf.write("BEGIN:VCARD\n")
                    f_vcf.write("VERSION:3.0\n")
                    f_vcf.write(f"FN:{contact_name}\n")       # 显示全名
                    f_vcf.write(f"N:;{contact_name};;;\n")    # 姓名结构化字段
                    f_vcf.write(f"TEL;TYPE=CELL:{phone}\n")   # 手机号
                    f_vcf.write("END:VCARD\n")
            print(f"📇 成功！已同步生成标准通讯录文件: {output_vcf} ，可直接导入手机。")
            
        else:
            print("\n❌ 未找到匹配的结果，未生成任何文件。")

# --- 运行交互 ---
if __name__ == "__main__":
    # 实例化（默认本地文件名和缓存文件名都为 phone.dat）
    guesser = PhoneDataGuesser("phone.dat")
    
    if guesser.records:
        print("\n" + "=" * 40)
        print("   手机号中间四位推测与VCF生成工具")
        print("=" * 40)
        
        p3 = input("请输入手机号前3位 (例如 139): ").strip()
        s4 = input("请输入手机号后4位 (例如 8888): ").strip()
        loc = input("请输入归属地关键字 (例如 杭州): ").strip()
        
        # 执行推测并同时保存 TXT 和 VCF 文件
        guesser.guess_and_save(p3, s4, loc)