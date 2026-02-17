from dash import dcc, html

dcc.Upload(
    id="upload-cdr",
    children=html.Div([
        "Drag and Drop or ",
        html.A("Select CDR File")
    ]),
    style={
        "width": "100%",
        "height": "60px",
        "lineHeight": "60px",
        "borderWidth": "2px",
        "borderStyle": "dashed",
        "borderRadius": "8px",
        "textAlign": "center",
        "margin": "10px"
    },
    multiple=False
)
