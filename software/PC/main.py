from multiprocessing import Process, Queue, set_start_method
from camara import iniciar_camara
from voz import deteccion_por_voz
from conexion import enviar_mensajes

if __name__ == "__main__":
    try:
        set_start_method("spawn")
    except RuntimeError:
        pass 
    
    colavoz = Queue()
    colacam = Queue()

    procesos = [
        Process(target=iniciar_camara, args=(colacam,)),
        Process(target=deteccion_por_voz, args=(colavoz,), daemon=True),
        Process(target=enviar_mensajes, args=(colavoz, colacam), daemon=True)
    ]

    for p in procesos:
        p.start()

    for p in procesos:
        p.join()