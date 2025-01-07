from xml.etree import ElementTree as ET
from xml.dom import minidom


# 載入你的 XML 文件
tree = ET.parse('Taiwan2.net.xml')  # 請將 'your_file.xml' 換成你的 XML 檔案路徑
root = tree.getroot()


# 初始化計數器與列表
cs_id_counter = 0  # 充電站 ID 計數器
charging_stations = []


# 遍歷 edge 元素
for edge in root.findall('edge'):
   edge_type = edge.get('type')
   # 過濾 type 是 primary, secondary 或 tertiary 的道路
   if edge_type in ['highway.primary', 'highway.secondary', 'highway.tertiary', 'highway.trunk','highway.primary_link', 'highway.secondary_link', 'highway.tertiary_link', 'highway.trunk_link']:
       added_charging = False  # 用來追蹤是否已為此 edge 添加充電站
       for lane in edge.findall('lane'):
           lane_length = float(lane.get('length'))
           lane_speed = float(lane.get('speed'))
           # 檢查 lane 的長度是否大於 200 並且該 edge 尚未添加充電站
           if lane_length > 200 and lane_speed <= 13.89 and not added_charging:
               lane_id = lane.get('id')
               charging_stations.append((f"cs_{cs_id_counter}", lane_id))
               cs_id_counter += 1
               added_charging = True  # 標記已為該 edge 添加充電站


# 創建新的 XML 文件結構
new_root = ET.Element("additional")


for cs_id, lane_id in charging_stations:
   ET.SubElement(new_root, "chargingStation", {
       "id": cs_id,
       "lane": lane_id,
       "startPos": "0.00",
       "endPos": "200.00",
       "chargeInTransit": "1",
       "power": "11700"
   })


# 將 XML 格式化並寫入文件
def prettify_and_write_xml(element, output_file):
   rough_string = ET.tostring(element, 'utf-8')
   reparsed = minidom.parseString(rough_string)
   with open(output_file, "w", encoding="utf-8") as f:
       f.write(reparsed.toprettyxml(indent="    "))


# 輸出排版過的 XML 檔案
output_path = 'charging_stations_add_Taiwan.xml'  # 儲存路徑
prettify_and_write_xml(new_root, output_path)


print(f"已成功生成格式化的充電站 XML 文件: {output_path}")