#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "aud0027_source_only",
    "AUD-0027 source-only compile control",
    -1,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC
PyInit_aud0027_source_only(void)
{
    return PyModule_Create(&module);
}
