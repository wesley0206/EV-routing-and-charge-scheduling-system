import networkx as nx
import random

def create_expanded_test_graphml():
    # 建立一個有向圖
    G = nx.DiGraph()

    # 添加起始和終點節點
    G.add_node("622617976")  # 起點
    G.add_node("622617959")  # 終點

    # 添加中間節點
    num_nodes = 400
    for i in range(1, num_nodes + 1):
        G.add_node(f"node_{i}")

    # 添加邊（確保起點到終點的路徑）
    previous_node = "622617976"
    for i in range(1, num_nodes + 1):
        current_node = f"node_{i}"
        G.add_edge(previous_node, current_node,
                   id=f"edge_{i}",
                   length=random.randint(100, 1000),
                   speed=random.randint(10, 30),
                   is_charging=bool(random.getrandbits(1)),
                   power=random.randint(0, 50))
        previous_node = current_node

    # 添加從最後一個中間節點到終點的邊
    G.add_edge(f"node_{num_nodes}", "622617959",
               id=f"edge_{num_nodes + 1}",
               length=random.randint(100, 1000),
               speed=random.randint(10, 30),
               is_charging=bool(random.getrandbits(1)),
               power=random.randint(0, 50))

    # 添加一些隨機邊以增加複雜性
    all_nodes = list(G.nodes)
    for _ in range(400):  # 添加額外的 400 條邊
        u, v = random.sample(all_nodes, 2)
        if not G.has_edge(u, v):  # 避免重複邊
            G.add_edge(u, v,
                       id=f"extra_edge_{random.randint(1, 10000)}",
                       length=random.randint(100, 1000),
                       speed=random.randint(10, 30),
                       is_charging=bool(random.getrandbits(1)),
                       power=random.randint(0, 50))

    # 將圖保存為 GraphML 文件
    nx.write_graphml(G, "test.graphml")

# 生成擴展的測試用 GraphML 文件
create_expanded_test_graphml()
