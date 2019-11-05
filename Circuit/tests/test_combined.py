import circuit

def test_combined():
    library = circuit.Library()
    ckt = circuit.Circuit()
    # Not registering subckt to library (though I really should)
    mysubckt = circuit.SubCircuit('mysubckt', 'pin1', 'pin2', param1=1, param2=1e-3, param3="0.1f", param4="hello")
    mysubckt.add_element(library['NMOS']('M1', 'pin1', 'net10', 'net13', 'vss'))
    mysubckt.add_element(library['NMOS']('M2', 'pin2', 'net10', 'net13', 'vss'))
    X1 = ckt.add_element(mysubckt('X1', 'net10', 'net12'))
    # Registering & reusing subckt from library (correct behavior)
    _ = circuit.SubCircuit('mysubckt2', 'pin1', 'pin2', 'pin3', library=library)
    library['mysubckt2'].add_element(library['NMOS']('M1', 'pin1', 'pin3', 'net13', 'vss'))
    library['mysubckt2'].add_element(library['NMOS']('M2', 'pin2', 'pin3', 'net13', 'vss'))
    X2 = ckt.add_element(library['mysubckt2']('X2', 'net10', 'net12', 'net14'))
    assert ckt.elements == [X1, X2]
    assert ckt.nets == ['net10', 'net12', 'net14']

def test_subckt_matching():
    # parse primitives
    parser = circuit.SpiceParser()
    with open('tests/basic_template.sp') as fp:
        parser.parse(fp.read())
    primitivelib = circuit.Library({x: y for x, y in parser.library.items() if issubclass(y, circuit.core._SubCircuit)})
    # parse netlist
    parser = circuit.SpiceParser()
    with open('tests/ota.sp') as fp:
        parser.parse(fp.read())
    # Perform subgraph matching & replacement
    ckt = parser.library['OTA']._circuit
    primitives = list(primitivelib.values())
    primitives.sort(key=lambda x: len(x.elements)*1000 - len(x._pins) - len(x.nets), reverse=True)
    assert len(ckt.elements) == 10
    assert all(x.name.startswith('M') for x in ckt.elements)
    ckt.replace_matching_subgraphs(primitives)
    assert len(ckt.elements) == 5
    assert all(x.name.startswith('X') for x in ckt.elements)