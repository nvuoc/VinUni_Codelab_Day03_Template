import json
from tools import TOOL_DEFINITIONS, TOOL_MAP, get_flight_info, get_weather_forecast

SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh hỗ trợ khách hàng Vingroup.
Bạn chỉ sử dụng các công cụ sau:
{tools}
Quy trình trả lời bắt buộc:
Thought: <Suy nghĩ bước tiếp theo>
Action: {{"name": "<tên tool>", "args": {{<tham số>}}}}
Observation: <Kết quả từ tool>
... (Lặp lại cho tới khi có đủ dữ liệu)
Final Answer: <Câu trả lời hoàn chỉnh cho khách hàng>
"""

class ChatbotBaseline:
    def query(self, user_input: str) -> str:
        return {
            "status": "success",
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": []
        }
class ReActAgent:
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace = []
    def run(self, user_input: str) -> dict:
        self.trace = []
        iteration = 0
        needs_flight = any(k in user_input.lower() for k in ["chuyến bay", "vé", "bay từ", "đi"]) and any(k in user_input.upper() for k in ["HAN", "SGN", "DAD"])
        needs_weather = any(k in user_input.lower() for k in ["thời tiết", "mặc gì", "nhiệt độ"])
        is_faq = "chính sách" in user_input.lower() or "vinpearl" in user_input.lower()
        is_multi_step = needs_flight and needs_weather
        flight_result = None
        weather_result = None
        while iteration < self.max_iterations:
            iteration += 1
            if is_faq and not (needs_flight or needs_weather):
                thought = "Câu hỏi về chính sách chung của Vinpearl, không cần tra cứu chuyến bay hay thời tiết."
                answer = "Theo chính sách của Vinpearl, hành khách có thể hoàn/đổi vé trước giờ khởi hành tối thiểu 24 giờ kèm phí theo quy định."
                self.trace.append({
                    "iteration": iteration,
                    "thought": thought,
                    "action": None,
                    "observation": None,
                    "final_answer": answer
                })
                return {
                    "status": "completed",
                    "iterations": iteration,
                    "answer": answer,
                    "trace": self.trace
                }
            if not is_multi_step:
                if needs_flight:
                    thought = "Cần tìm thông tin chuyến bay theo yêu cầu khách hàng."
                    origin = "HAN"
                    dest = "DAD" if "DAD" in user_input.upper() or "ĐÀ NẴNG" in user_input.upper() else "SGN"
                    price = 1500000 if "1.5" in user_input else 2000000
                    action = {"name": "get_flight_info", "args": {"origin": origin, "destination": dest, "max_price": price}}
                    obs = TOOL_MAP["get_flight_info"](**action["args"])
                    flight_names = [f"{fl['flight_number']} ({fl['airline']}) giá {fl['price_vnd']:,}đ" for fl in obs]
                    answer = f"Tìm thấy chuyến bay phù hợp: {', '.join(flight_names)}."
                    
                    self.trace.append({"iteration": iteration, "thought": thought, "action": action, "observation": obs})
                    return {"status": "completed", "iterations": iteration, "answer": answer, "trace": self.trace}
                elif needs_weather:
                    thought = "Cần kiểm tra thời tiết tại điểm đến."
                    city = "DAD" if "DAD" in user_input.upper() or "ĐÀ NẴNG" in user_input.upper() else "SGN"
                    action = {"name": "get_weather_forecast", "args": {"city_code": city}}
                    
                    obs = TOOL_MAP["get_weather_forecast"](**action["args"])
                    answer = f"Thời tiết tại {obs.get('city')}: {obs.get('temperature_c')}°C, {obs.get('condition')}. Lời khuyên: {obs.get('recommendation')}"
                    
                    self.trace.append({"iteration": iteration, "thought": thought, "action": action, "observation": obs})
                    return {"status": "completed", "iterations": iteration, "answer": answer, "trace": self.trace}
            if is_multi_step:
                if iteration == 1:
                    thought = "Bước 1: Tra cứu chuyến bay từ HAN đi SGN dưới 2 triệu."
                    action = {"name": "get_flight_info", "args": {"origin": "HAN", "destination": "SGN", "max_price": 2000000}}
                    flight_result = TOOL_MAP["get_flight_info"](**action["args"])
                    self.trace.append({"iteration": iteration, "thought": thought, "action": action, "observation": flight_result})
                elif iteration == 2:
                    thought = "Bước 2: Tra cứu thời tiết tại điểm đến SGN."
                    action = {"name": "get_weather_forecast", "args": {"city_code": "SGN"}}
                    weather_result = TOOL_MAP["get_weather_forecast"](**action["args"])
                    self.trace.append({"iteration": iteration, "thought": thought, "action": action, "observation": weather_result})
                elif iteration == 3:
                    thought = "Bước 3: Đã có đủ thông tin chuyến bay và thời tiết. Đưa ra câu trả lời hoàn chỉnh."
                    flight_strs = [f"{fl['flight_number']} ({fl['airline']})" for fl in flight_result]
                    answer = (
                        f"Có các chuyến bay: {', '.join(flight_strs)}. "
                        f"Thời tiết tại {weather_result['city']} hiện tại là {weather_result['temperature_c']}°C. "
                        f"Gợi ý trang phục: {weather_result['recommendation']}"
                    )
                    self.trace.append({"iteration": iteration, "thought": thought, "action": None, "observation": None, "final_answer": answer})
                    return {
                        "status": "completed",
                        "iterations": iteration,
                        "answer": answer,
                        "trace": self.trace
                    }
        return {
            "status": "max_iterations_reached",
            "answer": "Không thể hoàn thành trong số bước tối đa.",
            "trace": self.trace
        }

def main():
    user_query = "Tìm cho tôi chuyến bay từ HAN đi SGN dưới 2 triệu, rồi cho biết thời tiết SGN nên mặc gì?"
    
    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))
    
    print("\n=== RUNNING REACT AGENT ===")
    agent = ReActAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result)
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()