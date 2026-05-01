class Product:
    def __init__(self, product_id: int, color: str, size: int, created_time: int) -> None:
        self.id:                          int       = product_id
        self.color:                       str       = color
        self.size:                        int       = size
        self.created_time:                int       = created_time
        self.completed_time:              int       = 0
        self.current_task_arrival_time:   int       = 0
        self.current_process_arrival_time:int       = 0
        self.current_task_waiting_time:   int       = 0
        self.current_process_waiting_time:int       = 0

    def __repr__(self) -> str:
        return f"Product(id={self.id}, color={self.color})"