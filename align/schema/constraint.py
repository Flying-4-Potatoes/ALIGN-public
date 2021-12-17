import abc
import more_itertools as itertools
import re
import logging


from . import types
from .types import Union, Optional, Literal, List, set_context


logger = logging.getLogger(__name__)
pattern = re.compile(r'(?<!^)(?=[A-Z])')


def get_instances_from_hacked_dataclasses(constraint):
    assert constraint.parent.parent is not None, 'Cannot access parent scope'
    if hasattr(constraint.parent.parent, 'graph'):
        instances = {k for k, v in constraint.parent.parent.graph.nodes.items() if v['inst_type'] != 'net'}
    elif hasattr(constraint.parent.parent, 'elements'):
        instances = {x.name for x in constraint.parent.parent.elements}
    elif hasattr(constraint.parent.parent, 'instances'):
        instances = {x.instance_name for x in constraint.parent.parent.instances}
    else:
        raise NotImplementedError(f"Cannot handle {type(constraint.parent.parent)}")
    names = {x.name for x in constraint.parent if hasattr(x, 'name')}
    return set.union(instances, names)


def validate_instances(cls, value):
    # instances = cls._validator_ctx().parent.parent.instances
    instances = get_instances_from_hacked_dataclasses(cls._validator_ctx())
    assert isinstance(instances, set), 'Could not retrieve instances from subcircuit definition'
    assert all(x in instances or x.upper() in instances for x in value), f'One or more constraint instances {value} not found in {instances}'
    return [x.upper() for x in value]


def upper_case(cls, value):
    return [v.upper() for v in value]


class SoftConstraint(types.BaseModel):

    constraint: str

    def __init__(self, *args, **kwargs):
        constraint = pattern.sub(
            '_', self.__class__.__name__).lower()
        if 'constraint' not in kwargs or kwargs['constraint'] == self.__class__.__name__:
            kwargs['constraint'] = constraint
        else:
            assert constraint == kwargs[
                'constraint'], f'Unexpected `constraint` {kwargs["constraint"]} (expected {constraint})'
        super().__init__(*args, **kwargs)


class HardConstraint(SoftConstraint, abc.ABC):

    @abc.abstractmethod
    def translate(self, solver):
        '''
        Abstract Method for built in self-checks
          Every class that inherits from HardConstraint
          MUST implement this function.

        Function must yield a list of mathematical
          expressions supported by the 'solver'
          backend. This can be done using multiple
          'yield' statements or returning an iterable
          object such as list
        '''
        pass


class UserConstraint(HardConstraint, abc.ABC):

    @abc.abstractmethod
    def yield_constraints(self):
        '''
        Abstract Method to yield low level constraints
          Every class that inherits from UserConstraint
          MUST implement this function. This ensures
          clean separation of user-facing constraints
          from PnR constraints
        '''
        pass

    def translate(self, solver):
        for constraint in self.yield_constraints():
            yield from constraint.translate(solver)


class Order(HardConstraint):
    '''
    Defines a placement order for instances in a subcircuit.

    Args:
        instances (list[str]): List of :obj:`instances`
        direction (str, optional): The following options for direction are supported

            :obj:`'horizontal'`, placement order is left to right or vice-versa.

            :obj:`'vertical'`,  placement order is bottom to top or vice-versa.

            :obj:`'left_to_right'`, placement order is left to right.

            :obj:`'right_to_left'`, placement order is right to left.

            :obj:`'bottom_to_top'`, placement order is bottom to top.

            :obj:`'top_to_bottom'`, placement order is top to bottom.

            :obj:`None`: default (:obj:`'horizontal'` or :obj:`'vertical'`)
        abut (bool, optional): If `abut` is `True` adjoining instances will touch

    .. image:: ../images/OrderBlocks.PNG
        :align: center

    WARNING: `Order` does not imply aligment / overlap
    of any sort (See `Align`)

    Example: ::

        {"constraint":"Order", "direction": "left_to_right"}

    '''
    instances: List[str]
    direction: Optional[Literal[
        'horizontal', 'vertical',
        'left_to_right', 'right_to_left',
        'bottom_to_top', 'top_to_bottom'
    ]]
    abut: Optional[bool] = False

    @types.validator('instances', allow_reuse=True)
    def order_instances_validator(cls, value):
        assert len(value) >= 2, 'Must contain at least two instances'
        return validate_instances(cls, value)

    def translate(self, solver):

        def cc(b1, b2, c='x'):  # Create coordinate constraint
            if self.abut:
                return getattr(b1, f'ur{c}') == getattr(b2, f'll{c}')
            else:
                return getattr(b1, f'ur{c}') <= getattr(b2, f'll{c}')

        bvars = solver.iter_bbox_vars(self.instances)
        for b1, b2 in itertools.pairwise(bvars):
            if self.direction == 'left_to_right':
                yield cc(b1, b2, 'x')
            elif self.direction == 'right_to_left':
                yield cc(b2, b1, 'x')
            elif self.direction == 'bottom_to_top':
                yield cc(b1, b2, 'y')
            elif self.direction == 'top_to_bottom':
                yield cc(b2, b1, 'y')
            elif self.direction == 'horizontal':
                yield solver.Or(
                    cc(b1, b2, 'x'),
                    cc(b2, b1, 'x'))
            elif self.direction == 'vertical':
                yield solver.Or(
                    cc(b1, b2, 'y'),
                    cc(b2, b1, 'y'))
            else:
                yield solver.Or(
                    cc(b1, b2, 'x'),
                    cc(b2, b1, 'x'),
                    cc(b1, b2, 'y'),
                    cc(b2, b1, 'y'))


class Align(HardConstraint):
    '''
    `Instances` will be aligned along `line`. Could be
    strict or relaxed depending on value of `line`

    Args:
        instances (list[str]): List of `instances`
        line (str, optional): The following `line` values are currently supported:

            :obj:`h_any`, align instance's top, bottom or anything in between.

            :obj:`'v_any'`, align instance's left, right or anything in between.

            :obj:`'h_top'`, align instance's horizontally based on top.

            :obj:`'h_bottom'`, align instance's horizomtally based on bottom.

            :obj:`'h_center'`, align instance's horizontally based on center.

            :obj:`'v_left'`, align instance's vertically based on left.

            :obj:`'v_right'`, align instance's vertically based on right.

            :obj:`'v_center'`, align instance's vertically based on center.

            :obj:`None`:default (:obj:`'h_any'` or :obj:`'v_any'`).

    .. image:: ../images/AlignBlocks.PNG
        :align: center

    WARNING: `Align` does not imply ordering of any sort
    (See `Order`)

    Example: ::

        {"constraint":"Align", "line": "v_center"}

    '''
    instances: List[str]
    line: Optional[Literal[
        'h_any', 'h_top', 'h_bottom', 'h_center',
        'v_any', 'v_left', 'v_right', 'v_center'
    ]]

    _inst_validator = types.validator('instances', allow_reuse=True)(validate_instances)

    @types.validator('instances', allow_reuse=True)
    def align_instances_validator(cls, value):
        assert len(value) >= 2, 'Must contain at least two instances'
        return validate_instances(cls, value)

    def translate(self, solver):
        bvars = solver.iter_bbox_vars(self.instances)
        for b1, b2 in itertools.pairwise(bvars):
            if self.line == 'h_top':
                yield b1.ury == b2.ury
            elif self.line == 'h_bottom':
                yield b1.lly == b2.lly
            elif self.line == 'h_center':
                yield (b1.lly + b1.ury) / 2 == (b2.lly + b2.ury) / 2
            elif self.line == 'h_any':
                yield solver.Or(  # We don't know which bbox is higher yet
                    solver.And(b1.lly >= b2.lly, b1.ury <= b2.ury),
                    solver.And(b2.lly >= b1.lly, b2.ury <= b1.ury)
                )
            elif self.line == 'v_left':
                yield b1.llx == b2.llx
            elif self.line == 'v_right':
                yield b1.urx == b2.urx
            elif self.line == 'v_center':
                yield (b1.llx + b1.urx) / 2 == (b2.llx + b2.urx) / 2
            elif self.line == 'v_any':
                yield solver.Or(  # We don't know which bbox is wider yet
                    solver.And(b1.urx <= b2.urx, b1.llx >= b2.llx),
                    solver.And(b2.urx <= b1.urx, b2.llx >= b1.llx)
                )
            else:
                yield solver.Or(  # h_any OR v_any
                    solver.And(b1.urx <= b2.urx, b1.llx >= b2.llx),
                    solver.And(b2.urx <= b1.urx, b2.llx >= b1.llx),
                    solver.And(b1.lly >= b2.lly, b1.ury <= b2.ury),
                    solver.And(b2.lly >= b1.lly, b2.ury <= b1.ury)
                )


class Enclose(HardConstraint):
    '''
    Enclose `instances` within a flexible bounding box
    with `min_` & `max_` bounds

    Args:
        instances (list[str], optional): List of `instances`
        min_height (int, optional):  assign minimum height to the subcircuit
        max_height (int, optional):  assign maximum height to the subcircuit
        min_width (int, optional):  assign minimum width to the subcircuit
        max_width (int, optional):  assign maximum width to the subcircuit
        min_aspect_ratio (float, optional):  assign minimum aspect ratio to the subcircuit
        max_aspect_ratio (float, optional):  assign maximum aspect ratio to the subcircuit

    Note: Specifying any one of the following variables
    makes it a valid constraint but you may wish to
    specify more than one for practical purposes

    Example: ::

        {"constraint":"Enclose", "min_aspect_ratio": 0.1, "max_aspect_ratio": 10 }
    '''
    instances: Optional[List[str]]
    min_height: Optional[int]
    max_height: Optional[int]
    min_width: Optional[int]
    max_width: Optional[int]
    min_aspect_ratio: Optional[float]
    max_aspect_ratio: Optional[float]

    _inst_validator = types.validator('instances', allow_reuse=True)(validate_instances)

    @types.validator('max_aspect_ratio', allow_reuse=True)
    def bound_in_box_optional_fields(cls, value, values):
        assert value or any(
            getattr(values, x, None)
            for x in (
                'min_height',
                'max_height',
                'min_width',
                'max_width',
                'min_aspect_ratio'
            )
        ), 'Too many optional fields'
        return value

    def translate(self, solver):
        bb = solver.bbox_vars(solver.label(self))
        if self.min_width:
            yield bb.urx - bb.llx >= self.min_width
        if self.min_height:
            yield bb.ury - bb.lly >= self.min_height
        if self.max_width:
            yield bb.urx - bb.llx <= self.max_width
        if self.max_height:
            yield bb.ury - bb.lly <= self.max_height
        if self.min_aspect_ratio:
            yield solver.cast(
                (bb.ury - bb.lly) / (bb.urx - bb.llx),
                float) >= self.min_aspect_ratio
        if self.max_aspect_ratio:
            yield solver.cast(
                (bb.ury - bb.lly) / (bb.urx - bb.llx),
                float) <= self.max_aspect_ratio
        bvars = solver.iter_bbox_vars(self.instances)
        for b in bvars:
            yield b.urx <= bb.urx
            yield b.llx >= bb.llx
            yield b.ury <= bb.ury
            yield b.lly >= bb.lly


class Spread(HardConstraint):
    '''
    Spread `instances` by forcing minimum spacing along
    `direction` if two instances overlap in other direction

    Args:
        instances (list[str]): List of `instances`
        direction (str, optional): Direction for placement spread.
            (:obj:`'horizontal'` or :obj:`'vertical'` or :obj:`None`)
        distance (int): Distance in nanometer

    WARNING: This constraint checks for overlap but
    doesn't enforce it (See `Align`)

    Example: ::

        {
            "constraint": "Spread",
            "instances": ['MN0', 'MN1', 'MN2'],
            "direction": horizontal,
            "distance": 100
        }
    '''

    instances: List[str]
    direction: Optional[Literal['horizontal', 'vertical']]
    distance: int  # in nm

    @types.validator('instances', allow_reuse=True)
    def spread_instances_validator(cls, value):
        assert len(value) >= 2, 'Must contain at least two instances'
        return validate_instances(cls, value)

    def translate(self, solver):

        def cc(b1, b2, c='x'):
            d = 'y' if c == 'x' else 'x'
            return solver.Implies(
                solver.And(  # overlap orthogonal to c
                    getattr(b1, f'ur{d}') > getattr(b2, f'll{d}'),
                    getattr(b2, f'ur{d}') > getattr(b1, f'll{d}'),
                ),
                solver.Abs(  # distance in c coords
                    (
                        getattr(b1, f'll{c}')
                        + getattr(b1, f'ur{c}')
                    ) - (
                        getattr(b2, f'll{c}')
                        + getattr(b2, f'ur{c}')
                    )
                ) >= self.distance * 2
            )

        bvars = solver.iter_bbox_vars(self.instances)
        for b1, b2 in itertools.pairwise(bvars):
            if self.direction == 'horizontal':
                yield cc(b1, b2, 'x')
            elif self.direction == 'vertical':
                yield cc(b1, b2, 'y')
            else:
                yield solver.Or(
                    cc(b1, b2, 'x'),
                    cc(b1, b2, 'y')
                )


class AssignBboxVariables(HardConstraint):
    bbox_name: str
    llx: int
    lly: int
    urx: int
    ury: int

    @types.validator('urx', allow_reuse=True)
    def x_is_valid(cls, value, values):
        assert value > values['llx'], f'Reflection is not supported yet'
        return value

    @types.validator('ury', allow_reuse=True)
    def y_is_valid(cls, value, values):
        assert value > values['lly'], f'Reflection is not supported yet'
        return value

    def translate(self, solver):
        bvar = solver.bbox_vars(self.bbox_name)
        yield bvar.llx == self.llx
        yield bvar.lly == self.lly
        yield bvar.urx == self.urx
        yield bvar.ury == self.ury


class AspectRatio(HardConstraint):
    """
    Define lower and upper bounds on aspect ratio (=width/height) of a subcircuit

    `ratio_low` <= width/height <= `ratio_high`

    Args:
        subcircuit (str) : Name of subciruit
        ratio_low (float): Minimum aspect ratio (default 0.1)
        ratio_high (float): Maximum aspect ratio (default 10)
        weight (int): Weigth of this constraint (default 1)

    Example: ::

        {"constraint": "AspectRatio", "ratio_low": 0.1, "ratio_high": 10, "weight": 1 }
    """
    subcircuit: str
    ratio_low: float = 0.1
    ratio_high: float = 10
    weight: int = 1

    @types.validator('ratio_low', allow_reuse=True)
    def ratio_low_validator(cls, value):
        assert value >= 0, f'AspectRatio:ratio_low should be greater than zero {value}'
        return value

    @types.validator('ratio_high', allow_reuse=True)
    def ratio_high_validator(cls, value, values):
        assert value > values['ratio_low'], f'AspectRatio:ratio_high {value} should be greater than ratio_low {values["ratio_low"]}'
        return value

    def translate(self, solver):
        bvar = solver.bbox_vars('subcircuit')
        yield solver.cast(bvar.urx-bvar.llx, float) >= self.ratio_low * solver.cast(bvar.ury-bvar.lly, float)
        yield solver.cast(bvar.urx-bvar.llx, float) < self.ratio_high * solver.cast(bvar.ury-bvar.lly, float)


class Boundary(HardConstraint):
    """
    Define `max_height` and/or `max_width` on a subcircuit in micrometers.

    Args:
        subcircuit (str) : Name of subcircuit
        max_width (float, Optional) = 10000
        max_height (float, Optional) = 10000

    Example: ::

        {"constraint": "Boundary", "subcircuit": "OTA", "max_height": 100 }
    """
    subcircuit: str
    max_width: Optional[float] = 10000
    max_height: Optional[float] = 10000

    @types.validator('max_width', allow_reuse=True)
    def max_width_validator(cls, value):
        assert value >= 0, f'Boundary:max_width should be greater than zero {value}'
        return value

    @types.validator('max_height', allow_reuse=True)
    def max_height_validator(cls, value):
        assert value >= 0, f'Boundary:max_height should be greater than zero {value}'
        return value

    def translate(self, solver):
        bvar = solver.bbox_vars('subcircuit')
        if self.max_width is not None:
            yield solver.cast(bvar.urx-bvar.llx, float) <= 1000*self.max_width  # in nanometer
        if self.max_height is not None:
            yield solver.cast(bvar.ury-bvar.lly, float) <= 1000*self.max_height  # in nanometer


class GroupBlocks(HardConstraint):
    """GroupBlocks

    Forces a hierarchy creation for group of instances.
    This brings the instances closer.
    This reduces the problem statement for placer thus providing
    better solutions.

    Args:
      instances (list[str]): List of :obj:`instances`
      name (str): alias for the list of :obj:`instances`

    Example: ::

        {
            "constraint":"GroupBlocks",
            "name": "group1",
            "instances": ["MN0", "MN1", "MN3"]
        }
    """
    name: str
    instances: List[str]
    style: Optional[Literal["tbd_interdigitated", "tbd_common_centroid"]]

    @types.validator('name', allow_reuse=True)
    def group_block_name(cls, value):
        assert value, 'Cannot be an empty string'
        return value.upper()

    def translate(self, solver):
        # Non-zero width / height
        bb = solver.bbox_vars(self.name)
        yield bb.llx < bb.urx
        yield bb.lly < bb.ury
        # Grouping into common bbox
        for b in solver.iter_bbox_vars(self.instances):
            yield b.urx <= bb.urx
            yield b.llx >= bb.llx
            yield b.ury <= bb.ury
            yield b.lly >= bb.lly
        instances = get_instances_from_hacked_dataclasses(self)
        for b in solver.iter_bbox_vars((x for x in instances if x not in self.instances)):
            yield solver.Or(
                b.urx <= bb.llx,
                bb.urx <= b.llx,
                b.ury <= bb.lly,
                bb.ury <= b.lly,
            )

# You may chain constraints together for more complex constraints by
#     1) Assigning default values to certain attributes
#     2) Using custom validators to modify attribute values
# Note: Do not implement translate() here as it may be ignored
#       by certain engines


class AlignInOrder(UserConstraint):
    '''
    Align `instances` on `line` ordered along `direction`

    Args:
        instances (list[str]): List of :obj:`instances`
        line (str, optional): The following `line` values are currently supported:

            :obj:`'top'`, align instance's horizontally based on top.

            :obj:`'bottom'`, align instance's horizomtally based on bottom.

            :obj:`'center'`, align instance's horizontally based on center.

            :obj:`'left'`, align instance's vertically based on left.

            :obj:`'right'`, align instance's vertically based on right.
        direction: The following `direction` values are supported:

            :obj: `'horizontal'`, left to right

            :obj: `'vertical'`, bottom to top

    Example: ::

        {
            "constraint":"Align",
            "instances": ["MN0", "MN1", "MN3"],
            "line": "center",
            "direction": "horizontal"
        }

    Note: This is a user-convenience constraint. Same
    effect can be realized using `Order` & `Align`

    '''
    instances: List[str]
    line: Literal[
        'top', 'bottom',
        'left', 'right',
        'center'
    ] = 'bottom'
    direction: Optional[Literal['horizontal', 'vertical']]
    abut: Optional[bool] = False

    @types.validator('direction', allow_reuse=True, always=True)
    def _direction_depends_on_line(cls, v, values):
        # Process unambiguous line values
        if values['line'] in ['bottom', 'top']:
            if v is None:
                v = 'horizontal'
            else:
                assert v == 'horizontal', \
                    f'direction is horizontal if line is bottom or top'
        elif values['line'] in ['left', 'right']:
            if v is None:
                v = 'vertical'
            else:
                assert v == 'vertical', \
                    f'direction is vertical if line is left or right'
        # Center needs both line & direction
        elif values['line'] == 'center':
            assert v, \
                'direction must be specified if line == center'
        return v

    def yield_constraints(self):
        with set_context(self._parent):
            yield Align(
                instances=self.instances,
                line=f'{self.direction[0]}_{self.line}'
            )
            yield Order(
                instances=self.instances,
                direction='left_to_right' if self.direction == 'horizontal' else 'top_to_bottom',
                abut=self.abut
            )


#
# list of 'SoftConstraint'
#
# Below is a list of legacy constraints
# that have not been hardened yet
#

class PlaceSymmetric(SoftConstraint):
    # TODO: Finish implementing this. Not registered to
    #       ConstraintDB yet
    '''
    Place instance / pair of `instances` symmetrically
    around line of symmetry along `direction`

    Note: This is a user-convenience constraint. Same
    effect can be realized using `Align` & `Group`

    For example:
    `instances` = [['1'], ['4', '5'], ['2', '3'], ['6']]
    `direction` = 'vertical'
       1   |  5 4  |   6   |  4 5  |   1   |  5 4
      4 5  |   1   |  5 4  |   6   |   6   |   1
      2 3  |  2 3  |  3 2  |   1   |  5 4  |   6
       6   |   6   |   1   |  2 3  |  2 3  |  3 2
    '''
    instances: List[List[str]]
    direction: Optional[Literal['horizontal', 'vertical']]

    @types.validator('instances', allow_reuse=True)
    def place_symmetric_instances_validator(cls, value):
        '''
        X = Align(2, 3, 'h_center')
        Y = Align(4, 5, 'h_center')
        Align(1, X, Y, 6, 'center')

        '''

        assert len(value) >= 1, 'Must contain at least one instance'
        assert all(isinstance(x, List) for x in value), f'All arguments must be of type list in {self.instances}'
        return value


class CompactPlacement(SoftConstraint):
    """CompactPlacement

    Defines snapping position of placement for all blocks in design.

    Args:
        style (str): Following options are available.

            :obj:`'left'`, Moves all instances towards left during post-processing of placement.

            :obj:`'right'`, Moves all instances towards right during post-processing of placement.

            :obj:`'center'`, Moves all instances towards center during post-processing of placement.

    Example: ::

        {"constraint": "CompactPlacement", "style": "center"}
    """
    style: Literal[
        'left', 'right',
        'center'
    ] = 'left'


class SameTemplate(SoftConstraint):
    """SameTemplate

    Makes identical copy of all isntances

    Args:
        instances (list[str]): List of :obj:`instances`

    Example: ::

        {"constraint":"SameTemplate", "instances": ["MN0", "MN1", "MN3"]}
    """
    instances: List[str]


class CreateAlias(SoftConstraint):
    """CreateAlias

    Creates an alias for list of instances. You can use this
    alias later while defining constraints

    Args:
      instances (list[str]): List of :obj:`instances`
      name (str): alias for the list of :obj:`instances`

    Example: ::

        {
            "constraint":"CreateAlias",
            "instances": ["MN0", "MN1", "MN3"],
            "name": "alias1"
        }
    """
    instances: List[str]
    name: str


class MatchBlocks(SoftConstraint):
    '''
    TODO: Can be replicated by Enclose??
    '''
    instances: List[str]


class PowerPorts(SoftConstraint):
    '''
    Defines power ports for each hieararchy

    Args:
        ports (list[str]): List of :obj:`ports`.
            The first port of top hierarchy will be used for power grid creation.
            Power ports are used to identify source and drain of transistors
            by identifying the terminal at higher potential.

    Example: ::

        {
            "constraint":"PowerPorts",
            "ports": ["VDD", "VDD1"],
        }
    '''
    ports: List[str]

    _upper_case = types.validator('ports', allow_reuse=True)(upper_case)


class GroundPorts(SoftConstraint):
    '''
    Ground port for each hieararchy

    Args:
        ports (list[str]): List of :obj:`ports`.
            The first port of top hierarchy will be used for ground grid creation.
            Power ports are used to identify source and drain of transistors
            by identifying the terminal at higher potential.

    Example: ::

        {
            "constraint": "GroundPorts",
            "ports": ["GND", "GNVD1"],
        }
    '''
    ports: List[str]

    _upper_case = types.validator('ports', allow_reuse=True)(upper_case)


class ClockPorts(SoftConstraint):
    '''
    Clock port for each hieararchy. These are used as stop-points
    during auto-constraint identification, means no constraint search
    will be done beyond the nets connected to these ports.

    Args:
        ports (list[str]): List of :obj:`ports`.

    Example: ::

        {
            "constraint": "ClockPorts",
            "ports": ["CLK1", "CLK2"],
        }
    '''
    ports: List[str]

    _upper_case = types.validator('ports', allow_reuse=True)(upper_case)


class DoNotUseLib(SoftConstraint):
    '''
    Primitive libraries which should not be used during hierarchy annotation.

    Args:
        libraries (list[str]): List of :obj:`libraries`.
        propagate: Copy this constraint to sub-hierarchies

    Example: ::

        {
            "constraint": "DoNotUseLib",
            "libraries": ["DP_NMOS", "INV"],
            "propagate": False
        }
    '''
    libraries: List[str]
    propagate: Optional[bool]


class IsDigital(SoftConstraint):
    '''
    Place this hierarchy as a digital hierarchy
    Forbids any preprocessing, auto-annotation,
    array-identification or auto-constraint generation

    Args:
        isTrue (bool): True/False.
        propagate: Copy this constraint to sub-hierarchies

    Example: ::

        {
            "constraint": "IsDigital",
            "isTrue": True,
            "propagate": False
        }
    '''
    isTrue: bool
    propagate: Optional[bool]


class AutoConstraint(SoftConstraint):
    '''
    Forbids/Allow any auto-constraint generation

    Args:
        isTrue (bool): True/False.
        propagate: Copy this constraint to sub-hierarchies

    Example: ::

        {
            "constraint": "AutoConstraint",
            "isTrue": True,
            "propagate": False
        }
    '''
    isTrue: bool
    propagate: Optional[bool]


class IdentifyArray(SoftConstraint):
    '''
    Forbids/Alow any array identification

    Args:
        isTrue (bool): True/False.
        propagate: Copy this constraint to sub-hierarchies

    Example: ::

        {
            "constraint": "IdentifyArray",
            "isTrue": True,
            "propagate": False
        }
    '''
    isTrue: bool
    propagate: Optional[bool]


class AutoGroupCaps(SoftConstraint):
    '''
    Forbids/Allow creation of arrays for symmetric caps

    Args:
        isTrue (bool): True/False.
        propagate: Copy this constraint to sub-hierarchies

    Example: ::

        {
            "constraint": "AutoGroupCaps",
            "isTrue": True,
            "propagate": False
        }
    '''
    isTrue: bool
    propagate: Optional[bool]


class FixSourceDrain(SoftConstraint):
    '''
    Forbids auto checking of source/drain terminals of transistors.
    If `True`, Traverses from power to ground and vice-versa to
    ensure (drain of NMOS/ source of PMOS) is at higher potential.

    Args:
        isTrue (bool): True/False.
        propagate: Copy this constraint to sub-hierarchies

    Example: ::

        {
            "constraint": "FixSourceDrain",
            "isTrue": True,
            "propagate": False
        }
    '''
    isTrue: bool
    propagate: Optional[bool]


class KeepDummyHierarchies(SoftConstraint):
    '''
    Removes any single instance hierarchies.

    Args:
        isTrue (bool): True/False.
        propagate: Copy this constraint to sub-hierarchies

    Example: ::

        {
            "constraint": "KeepDummyHierarchies",
            "isTrue": True,
            "propagate": False
        }
    '''
    isTrue: bool
    propagate: Optional[bool]


class MergeSeriesDevices(SoftConstraint):
    '''
    Allow stacking of series devices
    Only works on NMOS/PMOS/CAP/RES.

    Args:
        isTrue (bool): True/False.
        propagate: Copy this constraint to sub-hierarchies

    Example: ::

        {
            "constraint": "MergeSeriesDevices",
            "isTrue": True,
            "propagate": False
        }
    '''
    isTrue: bool
    propagate: Optional[bool]


class MergeParallelDevices(SoftConstraint):
    '''
    Allow merging of parallel devices.
    Only works on NMOS/PMOS/CAP/RES.

    Args:
        isTrue (bool): True/False.
        propagate: Copy this constraint to sub-hierarchies

    Example: ::

        {
            "constraint": "MergeParallelDevices",
            "isTrue": True,
            "propagate": False
        }
    '''
    isTrue: bool
    propagate: Optional[bool]


class DoNotIdentify(SoftConstraint):
    '''
    TODO: Can be replicated by Enclose??
    Auto generated constraint based on all intances which are constrained
    '''
    instances: List[str]


class SymmetricBlocks(SoftConstraint):
    """SymmetricBlocks

    Defines a symmetry constraint between pair of blocks.

    Args:
        pairs (list[list[str]]): List of pair of instances.
            A pair can have one :obj:`instance` or two instances,
            where single instance implies self-symmetry
        direction (str) : Direction for axis of symmetry.
        mirrot (bool) : True/ False, Mirror instances along line of symmetry

    .. image:: ../images/SymmetricBlocks.PNG
        :align: center

    Example: ::

        {
            "constraint" : "SymmetricBlocks",
            "pairs" : [["MN0","MN1"], ["MN2","MN3"],["MN4"]],
            "direction" : "vertical"
        }

    """
    pairs: List[List[str]]
    direction: Literal['H', 'V']

    @types.validator('pairs', allow_reuse=True)
    def pairs_validator(cls, value):
        '''
        X = Align(2, 3, 'h_center')
        Y = Align(4, 5, 'h_center')
        Align(1, X, Y, 6, 'center')

        '''
        instances = get_instances_from_hacked_dataclasses(cls._validator_ctx())
        for pair in value:
            assert len(pair) >= 1, 'Must contain at least one instance'
            assert len(pair) <= 2, 'Must contain at most two instances'
        value = [validate_instances(cls, pair) for pair in value]
        if not hasattr(cls._validator_ctx().parent.parent, 'elements'):
            # PnR stage VerilogJsonModule
            return value
        if len(cls._validator_ctx().parent.parent.elements) == 0:
            # skips the check while reading user constraints
            return value
        group_block_instances = [const.name for const in cls._validator_ctx().parent if isinstance(const, GroupBlocks)]
        for pair in value:
            # logger.debug(f"pairs {self.pairs} {self.parent.parent.get_element(pair[0])}")
            if len([ele for ele in pair if ele in group_block_instances]) > 0:
                # Skip check for group block elements as they are added later in the flow
                continue
            elif len(pair) == 2:
                assert cls._validator_ctx().parent.parent.get_element(pair[0]), f"element {pair[0]} not found in design"
                assert cls._validator_ctx().parent.parent.get_element(pair[1]), f"element {pair[1]} not found in design"
                assert cls._validator_ctx().parent.parent.get_element(pair[0]).parameters == \
                    cls._validator_ctx().parent.parent.get_element(pair[1]).parameters, \
                    f"Incorrent symmetry pair {pair} in subckt {cls._validator_ctx().parent.parent.name}"
        return value


class BlockDistance(SoftConstraint):
    '''
    TODO: Replace with Spread

    Places the instances with a fixed gap.
    Also used in situations when routing is congested.

    Args:
        abs_distance (int) : Distance between two blocks.
            The number should be multiple of pitch of
            lowest horizontal and vertical routing layer i.e., M2 and M1

    .. image:: ../images/HorizontalDistance.PNG
        :align: center

    Example: ::

        {
            "constraint" : "BlockDistance",
            "abs_distance" : 420
        }
    '''
    abs_distance: int


class VerticalDistance(SoftConstraint):
    '''
    TODO: Replace with Spread

    Places the instances with a fixed vertical gap.
    Also used in situations when routing is congested.

    Args:
        abs_distance (int) : Distance between two blocks.
            The number should be multiple of pitch of
            lowest horizontal routing layer i.e., M2

    .. image:: ../images/VerticalDistance.PNG
        :align: center

    Example: ::

        {
            "constraint" : "VerticalDistance",
            "abs_distance" : 84
        }

    '''
    abs_distance: int


class HorizontalDistance(SoftConstraint):
    '''
    TODO: Replace with Spread

    Places the instances with a fixed horizontal gap.
    Also used in situations when routing is congested.

    Args:
        abs_distance (int) : Distance between two blocks.
            The number should be multiple of pitch of
            lowest vertical routing layer i.e., M1

    .. image:: ../images/HorizontalDistance.PNG
        :align: center

    Example: ::

        {
            "constraint" : "HorizontalDistance",
            "abs_distance" : 80
        }

    '''
    abs_distance: int


class GuardRing(SoftConstraint):
    '''
    Adds guard ring for particular hierarchy.

    Args:
        guard_ring_primitives (str) : Places this instance across boundary of a hierarchy
        global_pin (str): connect the pin of guard ring to this pin, mostly ground pin
        block_name: Name of the hierarchy

    Example: ::

        {
            "constraint" : "GuardRing",
            "guard_ring_primitives" : "guard_ring",
            "global_pin
        }
    '''
    guard_ring_primitives: str
    global_pin: str
    block_name: str


class GroupCaps(SoftConstraint):
    '''GroupCaps
    Creates a common centroid cap using a combination
    of unit sized caps. It can be of multiple caps.

    Args:
        name (str): name for grouped caps
        instances (List[str]): list of cap :obj:`instances`
        unit_cap (str): Capacitance value in fF
        num_units (List[int]): Number of units for each capacitance instance
        dummy (bool):  Whether to fill in dummies or not

   Example: ::

        {
            "constraint" : "GroupCaps",
            "name" : "cap_group1",
            "instances" : ["C0", "C1", "C2"],
            "num_units" : [2, 4, 8],
            "dummy" : True
        }
    '''
    name: str  # subcircuit name
    instances: List[str]
    unit_cap: str  # cap value in fF
    num_units: List
    dummy: bool  # whether to fill in dummies


class NetConst(SoftConstraint):
    """NetConst

    Net based constraint. Shielding and critically can be defined.

    Args:
        nets (List[str]) : List of net names.
        shield (str, optional) : Name of net for shielding.
        criticality (int, optional) : Criticality of net.
            Higher criticality means the net would be routed first.

    Example: ::

        {
            "constraint" : "NetConst",
            "nets" : ["net1", "net2", "net3"],
            "shield" : "VSS",
            "criticality" : 10
        }
    """
    nets: List[str]
    shield: Optional[str]
    criticality: Optional[int]


class PortLocation(SoftConstraint):
    '''PortLocation
    Defines approximate location of the port.
    T (top), L (left), C (center), R (right), B (bottom)

    Args:
        ports (List[str]) : List of ports
        location (str): Literal::

            ['TL', 'TC', 'TR',
            'RT', 'RC', 'RB',
            'BL', 'BC', 'BR',
            'LB', 'LC', 'LT']

    Example ::

        {
            "constraint" : "PortLocation",
            "ports" : ["P0", "P1", "P2"],
            "location" : "TL"
        }
    '''
    ports: List
    location: Literal['TL', 'TC', 'TR',
                      'RT', 'RC', 'RB',
                      'BL', 'BC', 'BR',
                      'LB', 'LC', 'LT']


class SymmetricNets(SoftConstraint):
    '''SymmetricNets
    Defines two nets as symmetric.
    A symmetric net will also enforce a SymmetricBlock between blocks
    connected to the nets.

    Args:
        net1 (str) : Name on net1
        net2 (str) : Name of net2
        pins1 (List, Optional) : oredered list of connected pins to be matched
        pins2 (List, Optional) : oredered list of connected pins to be matched
        direction (str) : Literal ['H', 'V'], Horizontal or vertical line of symmetry

    Example ::

        {
            "constraint" : "SymmetricNets",
            "net1" : "net1"
            "net2" : "net2"
            "pins1" : ["block1/A", "block2/A", "port1"]
            "pins2" : ["block1/B", "block2/B", "port2"]
            "direction" : 'V'
        }
     '''

    net1: str
    net2: str
    pins1: Optional[List]
    pins2: Optional[List]
    direction: Literal['H', 'V']


class MultiConnection(SoftConstraint):
    '''MultiConnection
    Defines multiple parallel wires for a net.
    This constraint is used to reduce parasitics and
    Electro-migration (EM) violations

    Args:
        nets (List[str]) : List of nets
        multiplier (int): Number of parallel wires

    Example ::

        {
            "constraint" : "MultiConnection",
            "nets" : ["N1", "N2", "N3"],
            "multiplier" : 4
        }
    '''
    nets: List[str]
    multiplier: int


class DoNotRoute(SoftConstraint):
    nets: List[str]

    _upper_case = types.validator('nets', allow_reuse=True)(upper_case)


ConstraintType = Union[
    # ALIGN Internal DSL
    Order, Align,
    Enclose, Spread,
    AssignBboxVariables,
    AspectRatio,
    Boundary,
    # Additional User constraints
    AlignInOrder,
    # Legacy Align constraints
    # (SoftConstraints)
    CompactPlacement,
    SameTemplate,
    CreateAlias,
    GroupBlocks,
    MatchBlocks,
    DoNotIdentify,
    BlockDistance,
    HorizontalDistance,
    VerticalDistance,
    GuardRing,
    SymmetricBlocks,
    GroupCaps,
    NetConst,
    PortLocation,
    SymmetricNets,
    MultiConnection,
    DoNotRoute,
    # Setup constraints
    PowerPorts,
    GroundPorts,
    ClockPorts,
    DoNotUseLib,
    IsDigital,
    AutoConstraint,
    AutoGroupCaps,
    FixSourceDrain,
    KeepDummyHierarchies,
    MergeSeriesDevices,
    MergeParallelDevices,
    IdentifyArray
]


class ConstraintDB(types.List[ConstraintType]):

    @types.validate_arguments
    def append(self, constraint: ConstraintType):
        if hasattr(constraint, 'translate'):
            if self.parent._checker is None:
                self.parent.verify()
            self.parent.verify(formulae=self._translate_and_annotate(constraint, self.parent._checker))
        super().append(constraint)

    @types.validate_arguments
    def remove(self, constraint: ConstraintType):
        super().remove(constraint)

    def __init__(self, *args, **kwargs):
        super().__init__()
        # Constraints may need to access parent scope for subcircuit information
        # To ensure parent is set appropriately, force users to use append
        if '__root__' in kwargs:
            data = kwargs['__root__']
            del kwargs['__root__']
        elif len(args) == 1:
            data = args[0]
            args = tuple()
        else:
            assert len(args) == 0 and len(kwargs) == 0
            data = []
        # TODO: Shouldn't need to invalidate this
        #       Lots of thrash happening here
        self.parent._checker = None
        with set_context(self):
            for x in data:
                super().append(x)

    def checkpoint(self):
        self.parent._checker.checkpoint()
        return super().checkpoint()

    def _revert(self):
        self.parent._checker.revert()
        super()._revert()


def expand_user_constraints(const_list):
    for const in const_list:
        if hasattr(const, 'yield_constraints'):
            with types.set_context(const.parent):
                yield from const.yield_constraints()
        else:
            yield const
