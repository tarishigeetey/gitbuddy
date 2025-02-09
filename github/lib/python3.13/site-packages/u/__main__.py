import revel

import u


app = revel.App(
    nicename="u",
    command_name="u",
    version=u.__version__,
)


@app.command()
def make_derived_quantity(equation: str) -> None:
    revel.print("FIXME:", equation)


app.run()
