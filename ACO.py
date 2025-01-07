import random
import networkx as nx
import numpy as np
from scheduling import v2g_milp_optimize

# 讀取圖形文件
graphml_file = "Taiwan.graphml"
G = nx.read_graphml(graphml_file)

# 參數設置
start_node = "-144866"
end_node = "-212207"
initial_soc = 80  # 起始電量 (百分比)
target_soc = 90   # 目標電量 (百分比)
maximum_power = 60000  # 電池最大容量 (Wh)
max_time = 3600 * 2     # 2 小時
charging_cost_per_kWh_peak = 0.3
charging_cost_per_kWh_offpeak = 0.2
energy_consumption_per_m = 0.2  # 每米耗電量 (Wh)
charging_station_power = 80     # kW (僅做參考, 交給v2g演算法更詳細處理)
power_track_power = 12          # kW
power_track_length = 200        # m

# 螞蟻群算法參數
num_ants = 300
iterations = 300
alpha = 4
beta = 4
rho = 0.1
Q = 100
min_pheromone = 1e-6

visited_nodes = {}


#############################
# ACO邏輯與輔助函式
#############################

def initialize_pheromone(G):
    pheromone = {}
    for u, v in G.edges():
        # 一般路徑
        pheromone[(u, v)] = 1.0

        # 若 u 是充電站 => 初始化充電行為的費洛蒙
        if G.nodes[u].get('is_charging_station', False):
            # 這裡示範一些常見停留時間 + SOC
            pheromone[(u, 'charging')] = {
                (0, 80): 1.0,
                (15, 80): 1.0,
                (15, 90): 1.0,
                (30, 80): 1.0,
                (30, 90): 1.0,
                (45, 80): 1.0,
                (45, 90): 1.0,
                (60, 80): 1.0,
                (60, 90): 1.0,
            }
    return pheromone

def calculate_distance(u, v):
    return G[u][v].get('length', 1)

def calculate_energy_consumption(u, v):
    return calculate_distance(u, v) * energy_consumption_per_m

def calculate_travel_time(u, v):
    return G[u][v].get('travel_time', 0)

def calculate_pt_energy_gain(u, v):
    return power_track_length / G[u][v].get('speed', 1) * power_track_power / 3600


###############
# 改善1: 道路啟發式
###############
def heuristic_road(u, v, current_soc):
    """
    同時考慮:
     - 該段 travel_time
     - 預估的行駛電費
     - visit_count (避免重複拜訪)
    """
    travel_time = calculate_travel_time(u, v)
    visit_count = visited_nodes.get(v, 0)

    # 預估耗電
    energy_consumption = calculate_energy_consumption(u, v)

    # 假設此時是尖峰 or 離峰
    # (簡單用 current time 這邊可能不準, 但示範)
    # 這裡僅示範, 假設螞蟻不知道精確時間, 或可以傳入Ant的time_spent
    # 為了簡單化, 先假設全用peak
    driving_cost_rate = charging_cost_per_kWh_peak
    # 也可根據 current_soc / some rule 來決定能不能走得動...(此處略)

    driving_cost = (energy_consumption/1000.0) * driving_cost_rate

    # 綜合指標 (可調參數λ,μ)
    # 數值越小代表「越不吸引螞蟻」, 故啟發值要用 1/(...) 形式
    combined_factor = travel_time + 10*driving_cost + 5*visit_count
    if combined_factor <= 0:
        combined_factor = 0.1

    return 1.0 / combined_factor


###############
# 改善2: 充電決策啟發式
###############
def estimate_charging_cost(time_spent, option_time_min, current_soc, option_target_soc):
    """
    一個示範函式:
     - 先假設要停 option_time_min 分鐘, 並從 current_soc => option_target_soc
     - 用 v2g_optimize 做一次 "試算" => 得到預估cost
    """
    status, cost, _ = v2g_milp_optimize(
        time_spent,
        option_time_min,
        current_soc,
        option_target_soc,
    )
    return status, cost

class Ant:
    def __init__(self, start_node, end_node):
        self.path = [start_node]
        self.soc = initial_soc
        self.time_spent = 0
        self.current_node = start_node
        self.end_node = end_node
        self.total_cost = 0
        self.charging_cost = 0
        self.stations_log = []
        # 新增: 為了路段啟發式, 你可能需要保留"move"時動態判斷peak/offpeak
        # 這裡先省略不做.

    def move(self, pheromone, alpha, beta):
        # 選下一個節點
        next_node = self.select_next_node(pheromone, alpha, beta)
        visited_nodes[next_node] = visited_nodes.get(next_node, 0) + 1
        self.path.append(next_node)

        # 處理道路行駛耗電
        if G[self.path[-2]][self.path[-1]].get('is_charging', False):
            pt_charging = calculate_pt_energy_gain(self.path[-2], self.path[-1])
            energy_consumption = calculate_energy_consumption(self.path[-2], self.path[-1]) - pt_charging
            # 判斷尖峰/離峰(示範)
            if self.time_spent < 1.5 * 3600:
                cost_rate = charging_cost_per_kWh_peak
            else:
                cost_rate = charging_cost_per_kWh_offpeak

            charging_cost = pt_charging * cost_rate / 1000
            self.charging_cost += charging_cost
            self.total_cost += charging_cost
            self.soc += (pt_charging / maximum_power) * 100
        else:
            energy_consumption = calculate_energy_consumption(self.path[-2], self.path[-1])

        travel_time = calculate_travel_time(self.path[-2], self.path[-1])
        self.time_spent += travel_time
        self.soc -= energy_consumption / maximum_power * 100

        # 行駛耗電費用
        if self.time_spent < 1.5 * 3600:
            driving_cost_rate = charging_cost_per_kWh_peak
        else:
            driving_cost_rate = charging_cost_per_kWh_offpeak
        driving_cost = (energy_consumption / 1000.0) * driving_cost_rate
        self.total_cost += driving_cost

        # 更新節點
        self.current_node = next_node

        # 若是充電站 => handle_charging_station
        if G.nodes[next_node].get('is_charging_station', False):
            self.handle_charging_station(pheromone, alpha, beta)

    def handle_charging_station(self, pheromone, alpha, beta):
        all_options = list(pheromone[(self.current_node, 'charging')].keys())
        
        feasible_options = []
        probabilities = []

        for (option_time_min, option_target_soc) in all_options:
            # 1) 確保最終 SOC >= 20%
            if option_target_soc < self.soc:
                continue
            
            if option_target_soc < 20:
                continue

            # 2) 取對應的費洛蒙
            pheromone_strength = pheromone[(self.current_node, 'charging')][(option_time_min, option_target_soc)]

            # === 新增: 預估此選項的充電成本, 做為啟發式依據 ===
            status, est_cost = estimate_charging_cost(self.time_spent, option_time_min, self.soc, option_target_soc)
            if status == 'Infeasible':
                continue
            
            if est_cost < 0:
                # 表示放電收益, 可能很讚 => 給更高的吸引力
                # (加個微小 offset避免分母0)
                est_cost_value = 0.5  # 代表很有利
            else:
                est_cost_value = est_cost + 1.0
            
            # 啟發值 = 1 / (est_cost + 1)
            # => cost 越小 => 1/(小+1) 越大
            heuristic_strength = 1.0 / est_cost_value

            # 綜合 "費洛蒙" 和 "啟發式"
            probabilities.append((pheromone_strength ** alpha) * (heuristic_strength ** beta))
            feasible_options.append((option_time_min, option_target_soc))

        if not feasible_options:
            # 沒有可行選項就不充電
            return

        total_prob = sum(probabilities)
        probabilities = [p / total_prob for p in probabilities] if total_prob > 0 else [1 / len(probabilities)] * len(probabilities)

        chosen_idx = random.choices(range(len(feasible_options)), probabilities)[0]
        chosen_time_min, chosen_target_soc = feasible_options[chosen_idx]

        if chosen_time_min > 0:
            stop_time_sec = chosen_time_min * 60

            # 呼叫 V2G 最佳化: 可能充電或放電
            _, cost, delta_soc = v2g_milp_optimize(
                self.time_spent,
                chosen_time_min,
                self.soc,
                chosen_target_soc,
            )
            
            old_soc = self.soc
            self.soc += delta_soc
            self.time_spent += stop_time_sec
            self.total_cost += cost
            self.charging_cost += cost

            # === 在這裡就把「選擇的 (time, targetSOC)」記下來 ===
            # 不用去對 final_soc
            self.stations_log.append({
                "station": self.current_node,
                "chosen_time_min": chosen_time_min,
                "chosen_target_soc": chosen_target_soc,
                "initial_soc": old_soc,
                "final_soc": self.soc,
                "cost": cost,
            })

    def select_next_node(self, pheromone, alpha, beta):
        neighbors = list(G.neighbors(self.current_node))
        probabilities = []
        feasible_neighbors = []
        for neighbor in neighbors:
            pheromone_strength = pheromone.get((self.current_node, neighbor), min_pheromone)

            # 使用新的 "heuristic_road"
            heuristic_strength = heuristic_road(self.current_node, neighbor, self.soc)

            probabilities.append((pheromone_strength ** alpha) * (heuristic_strength ** beta))
            feasible_neighbors.append(neighbor)

        total_prob = sum(probabilities)
        probabilities = [p / total_prob for p in probabilities] if total_prob > 0 else [1 / len(probabilities)] * len(probabilities)

        chosen_neighbor = random.choices(feasible_neighbors, probabilities)[0]
        return chosen_neighbor


def run_aco():
    pheromone = initialize_pheromone(G)

    best_path = None
    best_cost = float('inf')
    best_log = []
    best_charging_cost = float('inf')
    best_time = None
    final_soc_val = None

    for iteration in range(iterations):
        ants = [Ant(start_node, end_node) for _ in range(num_ants)]

        for ant in ants:
            while ant.current_node != end_node and ant.soc > 20 and ant.time_spent < max_time:
                ant.move(pheromone, alpha, beta)

            if ant.current_node == end_node and ant.soc >= target_soc:
                print(ant.path)
                if ant.total_cost < best_cost:
                    best_path = ant.path
                    best_cost = ant.total_cost
                    best_log = ant.stations_log
                    best_charging_cost = ant.charging_cost
                    best_time = ant.time_spent
                    final_soc_val = ant.soc

        # --- 費洛蒙更新 ---
        for ant in ants:
            if ant.current_node == end_node:
                # 路徑上每條邊都加費洛蒙
                print(ant.path)
                for i in range(len(ant.path) - 1):
                    edge = (ant.path[i], ant.path[i + 1])
                    if edge not in pheromone:
                        pheromone[edge] = min_pheromone
                    pheromone[edge] = max(
                        pheromone[edge] + Q / ant.total_cost,
                        min_pheromone
                    )
                
                # 充電行為的費洛蒙更新
                for log_item in ant.stations_log:
                    station = log_item['station']
                    chosen_time_min = log_item['chosen_time_min']
                    chosen_target_soc = log_item['chosen_target_soc']
                    
                    if (station, 'charging') in pheromone:
                        if (chosen_time_min, chosen_target_soc) in pheromone[(station, 'charging')]:
                            pheromone[(station, 'charging')][(chosen_time_min, chosen_target_soc)] = max(
                                pheromone[(station, 'charging')][(chosen_time_min, chosen_target_soc)] + Q / ant.total_cost,
                                min_pheromone
                            )

        # --- 費洛蒙揮發 ---
        for edge in pheromone:
            if isinstance(pheromone[edge], dict):
                # 充電行為
                for option in pheromone[edge]:
                    pheromone[edge][option] = max(pheromone[edge][option] * (1 - rho), min_pheromone)
            else:
                # 一般路徑
                pheromone[edge] = max(pheromone[edge] * (1 - rho), min_pheromone)

    return best_path, best_cost, best_charging_cost, best_log, best_time, final_soc_val


# 執行
best_path, best_cost, best_charging_cost, best_log, best_time, final_soc = run_aco()

print("Best Path:", best_path)
print("Best Cost:", best_cost)
print("Best Charging Cost:", best_charging_cost)
print("Stations Log:", best_log)
print("Total Time Spent:", best_time, "seconds")
print("Final SOC:", final_soc, "%")
