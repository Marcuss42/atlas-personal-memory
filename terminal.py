# from ai.agent import Atlas


# class Interface:
#     def __init__(self):
#         self.atlas = Atlas()
#         self.conversation_id = self.atlas.memory.create_conversation()

#     def executar(self):
#         while True:
#             try:
#                 mensagem = input("Você: ")
#             except (KeyboardInterrupt, EOFError):
#                 print()
#                 break

#             mensagem = mensagem.strip()

#             if not mensagem:
#                 continue

#             if mensagem.lower() == "sair":
#                 break

#             try:
#                 resposta = self.atlas.process_message(
#                     self.conversation_id,
#                     mensagem
#                 )
#                 print(f"Atlas: {resposta}")
#             except Exception:
#                 print("Atlas: ocorreu um erro. Consulte os logs.")


# if __name__ == "__main__":
#     Interface().executar()

import shutil
from pathlib import Path


class Interface:
    def __init__(self):
        logs_dir = Path(__file__).resolve().parent / "logs"

        if logs_dir.exists():
            shutil.rmtree(logs_dir)

        from ai.agent import Atlas

        self.atlas = Atlas()
        self.conversation_id = self.atlas.memory.create_conversation()

    def executar(self):
        while True:
            try:
                mensagem = input("Você: ")
            except (KeyboardInterrupt, EOFError):
                print()
                break

            mensagem = mensagem.strip()

            if not mensagem:
                continue

            if mensagem.lower() == "sair":
                break

            try:
                resposta = self.atlas.process_message(
                    self.conversation_id,
                    mensagem
                )
                print(f"Atlas: {resposta}")
            except Exception:
                print("Atlas: ocorreu um erro. Consulte os logs.")


if __name__ == "__main__":
    Interface().executar()