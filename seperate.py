import xml.etree.ElementTree as ET

def split_charge_in_transit(input_file, output_file_with_charge, output_file_without_charge):
    # 讀取原始 XML 文件
    tree = ET.parse(input_file)
    root = tree.getroot()

    # 建立兩個新的 XML 根節點
    root_with_charge = ET.Element(root.tag)
    root_without_charge = ET.Element(root.tag)

    # 遍歷所有子節點，按條件分類
    for elem in root:
        if elem.attrib.get("chargeInTransit") == "1":
            root_with_charge.append(elem)  # chargeInTransit='1'
        else:
            root_without_charge.append(elem)  # 其他元素

    # 將有 chargeInTransit='1' 的元素保存到指定文件
    tree_with_charge = ET.ElementTree(root_with_charge)
    tree_with_charge.write(output_file_with_charge, encoding="utf-8", xml_declaration=True)

    # 將沒有 chargeInTransit='1' 的元素保存到另一個文件
    tree_without_charge = ET.ElementTree(root_without_charge)
    tree_without_charge.write(output_file_without_charge, encoding="utf-8", xml_declaration=True)

# 使用範例
input_file = "charging_stations_add_Taiwan.xml"  # 原始 XML 文件
output_file_with_charge = "power_track_add_Taiwan.xml"  # 含有 chargeInTransit='1' 的元素
output_file_without_charge = "charging_stations_add_Taiwan.xml"  # 不含 chargeInTransit='1' 的元素

split_charge_in_transit(input_file, output_file_with_charge, output_file_without_charge)
