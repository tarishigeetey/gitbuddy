from langchain_core.tools import tool

@tool
def note_tool(note):
    """
    saves a note in local file

    Args:
       note: the ttext note to save
    """

    with open("notes.txt", "a") as f:
        f.write(note + "/n")