from __future__ import absolute_import

from langkit import compiled_types
from langkit.compiled_types import (
    ASTNode, BoolType, EnumType, Field, Struct, UserField, abstract,
    env_metadata, root_grammar_class, LongType, create_macro, TypeRepo,
    LogicVarType
)

from langkit.envs import EnvSpec
from langkit.expressions import (
    AbstractProperty, And, Or, EmptyEnv, Env, EnvGroup, Let, Literal, No, Not,
    langkit_property, Var
)
from langkit.expressions import New
from langkit.expressions import Property
from langkit.expressions import Self
from langkit.expressions.boolean import If
from langkit.expressions.logic import Domain

T = TypeRepo()


def symbol_list(base_id_list):
    """
    Turn a list of BaseId into the corresponding array of symbols.

    :param AbstractExpression base_id_list: ASTList for the BaseId nodes to
        process.
    :rtype: AbstractExpression
    """
    return base_id_list.map(lambda base_id: base_id.tok.symbol)


@env_metadata
class Metadata(Struct):
    dottable_subprogram = UserField(
        BoolType, doc="Whether the stored element is a subprogram accessed "
                      "through the dot notation"
    )
    implicit_deref = UserField(
        BoolType, doc="Whether the stored element is accessed through an "
                      "implicit dereference"
    )


@abstract
@root_grammar_class
class AdaNode(ASTNode):
    """
    Root node class for the Ada grammar. This is good and necessary for several
    reasons:

    1. It will facilitate the sharing of langkit_support code if we ever have
       two libraries generated by LanguageKit in the same application.

    2. It allows to insert code specific to the ada root node, without
       polluting every LanguageKit node, and without bringing back the root
       ASTNode in the code templates.
    """

    ref_var = UserField(LogicVarType, is_private=True)
    type_var = UserField(LogicVarType, is_private=True)
    """
    Those two fields represents the result of the xref equations solving.

    TODO: They're probably not needed on every AdaNode, but are put here for
    the time being for convenience. We'll need to hoist them up the type chain
    at some point.
    """


def child_unit(name_expr, scope_expr, env_val_expr=Self):
    """
    This macro will add the properties and the env specification necessary
    to make a node implement the specification of a library child unit in
    Ada, so that you can declare new childs to an unit outside of its own
    scope.

    :param AbstractExpression name_expr: The expression that will retrieve
        the name symbol for the decorated node.

    :param AbstractExpression scope_expr: The expression that will retrieve the
        scope node for the decorated node.

    :param AbstractExpression env_val_expr: The expression that will
        retrieve the environment value for the decorated node.

    :rtype: NodeMacro
    """

    attribs = dict(
        scope=Property(scope_expr, private=True, doc="""
                       Helper property, that will return the scope of
                       definition of this child unit.
                       """),
        env_spec=EnvSpec(
            initial_env=Self.scope, add_env=True,
            add_to_env=(name_expr, env_val_expr)
        )
    )

    return create_macro(attribs)


@abstract
class BasicDecl(AdaNode):
    defining_names = AbstractProperty(type=T.Name.array_type())
    defining_name = Property(Self.defining_names.at(0))
    defining_env = Property(
        EmptyEnv, private=True,
        doc="""
        Return a lexical environment that contains entities that are accessible
        as suffixes when Self is a prefix.
        """
    )

    array_ndims = Property(
        Literal(0),
        doc="""
        If this designates an entity with an array-like interface, return its
        number of dimensions. Return 0 otherwise.
        """
    )
    is_array = Property(Self.array_ndims > 0)


@abstract
class Body(BasicDecl):
    pass


@abstract
class BodyStub(Body):
    pass


class DiscriminantSpec(AdaNode):
    ids = Field()
    type_expr = Field()
    default_expr = Field()

    env_spec = EnvSpec(add_to_env=(symbol_list(Self.ids), Self))


class TypeDiscriminant(AdaNode):
    discr_specs = Field()


@abstract
class TypeDef(AdaNode):
    array_ndims = Property(
        Literal(0),
        doc="""
        If this designates an array type, return its number of dimensions.
        Return 0 otherwise.
        """
    )


class EnumTypeDef(TypeDef):
    enum_literals = Field()


class Variant(AdaNode):
    choice_list = Field()
    components = Field()


class VariantPart(AdaNode):
    discr_name = Field()
    variant = Field()


class ComponentDecl(BasicDecl):
    ids = Field()
    component_def = Field()
    default_expr = Field()
    aspects = Field()

    env_spec = EnvSpec(add_to_env=(symbol_list(Self.ids), Self))

    defining_env = Property(
        Self.component_def.type_expr.defining_env,
        private=True,
        doc="See BasicDecl.defining_env"
    )

    defining_names = Property(Self.ids.map(lambda id: id.cast(T.Name)))

    array_ndims = Property(Self.component_def.type_expr.array_ndims)


class ComponentList(AdaNode):
    components = Field()
    variant_part = Field()


class RecordDef(AdaNode):
    components = Field()


class RecordTypeDef(TypeDef):
    abstract = Field()
    tagged = Field()
    limited = Field()
    record_def = Field()


@abstract
class RealTypeDef(TypeDef):
    pass


@abstract
class TypeDecl(BasicDecl):
    type_id = Field()

    name = Property(Self.type_id)
    env_spec = EnvSpec(add_to_env=(Self.type_id.name.symbol, Self),
                       add_env=True)

    defining_names = Property(Self.type_id.cast(T.Name).singleton)


class FullTypeDecl(TypeDecl):
    discriminants = Field()
    type_def = Field()
    aspects = Field()

    array_ndims = Property(Self.type_def.array_ndims)

    @langkit_property()
    def defining_env():
        # The environments that types define are always independent of the
        # environment in which the type is defined, hence the orphan
        # environment.
        result = Self.children_env.env_orphan

        return Self.type_def.match(
            # If this type derives from another one, it inherits the latter's
            # environment, so the following will return a copy of result whose
            # parent environment is the inheritted one.
            lambda td=DerivedTypeDef: EnvGroup(result, td.name.defining_env),

            lambda _:                 result,
        )


class FloatingPointDef(RealTypeDef):
    num_digits = Field()
    range = Field()


class OrdinaryFixedPointDef(RealTypeDef):
    delta = Field()
    range = Field()


class DecimalFixedPointDef(RealTypeDef):
    delta = Field()
    digits = Field()
    range = Field()


@abstract
class Constraint(AdaNode):
    pass


class RangeConstraint(Constraint):
    range = Field()


class DigitsConstraint(Constraint):
    digits = Field()
    range = Field()


class DeltaConstraint(Constraint):
    digits = Field()
    range = Field()


class IndexConstraint(Constraint):
    constraints = Field()


class DiscriminantConstraint(Constraint):
    constraints = Field()


class DiscriminantAssociation(Constraint):
    ids = Field()
    expr = Field()


class DerivedTypeDef(TypeDef):
    abstract = Field()
    limited = Field()
    synchronized = Field()
    null_exclusion = Field()
    name = Field()
    constraint = Field()
    interfaces = Field()
    record_extension = Field()
    has_private_part = Field()

    array_ndims = Property(Self.name.array_ndims)


class IncompleteTypeDef(TypeDef):
    is_tagged = Field()

    # TODO: what should we return for array_ndims? Do we need to find the full
    # view?


class PrivateTypeDef(TypeDef):
    abstract = Field()
    tagged = Field()
    limited = Field()

    # TODO: what should we return for array_ndims? Do we need to find the full
    # view?


class SignedIntTypeDef(TypeDef):
    range = Field()


class ModIntTypeDef(TypeDef):
    expr = Field()


@abstract
class ArrayIndices(AdaNode):
    ndims = AbstractProperty(
        type=LongType,
        doc="""Number of dimensions described in this node."""
    )


class UnconstrainedArrayIndices(ArrayIndices):
    list = Field()

    ndims = Property(Self.list.length)


class ConstrainedArrayIndices(ArrayIndices):
    list = Field()

    ndims = Property(Self.list.length)


class ComponentDef(AdaNode):
    aliased = Field()
    type_expr = Field()


class ArrayTypeDef(TypeDef):
    indices = Field()
    stored_component = Field()

    array_ndims = Property(Self.indices.ndims)


class InterfaceKind(EnumType):
    alternatives = ["limited", "task", "protected", "synchronized"]
    suffix = 'interface'


class InterfaceTypeDef(TypeDef):
    interface_kind = Field()
    interfaces = Field()


class SubtypeDecl(TypeDecl):
    type_expr = Field()
    aspects = Field()

    array_ndims = Property(Self.type_expr.array_ndims)
    defining_env = Property(Self.type_expr.defining_env)


class TaskDef(AdaNode):
    interfaces = Field()
    items = Field()
    private_items = Field()
    end_id = Field()


class ProtectedDef(AdaNode):
    public_ops = Field()
    private_components = Field()
    end_id = Field()


class TaskTypeDecl(BasicDecl):
    task_type_name = Field()
    discrs = Field()
    aspects = Field()
    definition = Field()

    defining_names = Property(Self.task_type_name.cast(T.Name).singleton)


class ProtectedTypeDecl(BasicDecl):
    protected_type_name = Field()
    discrs = Field()
    aspects = Field()
    interfaces = Field()
    definition = Field()

    defining_names = Property(Self.protected_type_name.cast(T.Name).singleton)


class AccessDef(TypeDef):
    not_null = Field()
    access_expr = Field()
    constraint = Field()


class FormalDiscreteTypeDef(TypeDef):
    pass


class NullComponentDecl(AdaNode):
    pass


class WithDecl(AdaNode):
    is_limited = Field()
    is_private = Field()
    packages = Field()


@abstract
class UseDecl(AdaNode):
    pass


class UsePkgDecl(UseDecl):
    packages = Field()


class UseTypDecl(UseDecl):
    all = Field()
    types = Field()


class TypeExpression(AdaNode):
    """
    This type will be used as a base for what represents a type expression
    in the Ada syntax tree.
    """
    null_exclusion = Field()
    type_expr_variant = Field()

    array_ndims = Property(Self.type_expr_variant.array_ndims)
    defining_env = Property(
        Self.type_expr_variant.defining_env, private=True,
        doc='Helper for BaseDecl.defining_env'
    )


@abstract
class TypeExprVariant(AdaNode):
    array_ndims = AbstractProperty(
        type=LongType,
        doc="""
        If this designates an array type, return its number of dimensions.
        Return 0 otherwise.
        """
    )
    defining_env = Property(
        EmptyEnv, private=True,
        doc='Helper for BaseDecl.defining_env'
    )


class TypeRef(TypeExprVariant):
    name = Field()
    constraint = Field()

    # The name for this type has to be evaluated in the context of the TypeRef
    # node itself: we don't want to use whatever lexical environment the caller
    # is using.
    designated_type = Property(
        Self.node_env.eval_in_env(Self.name.designated_type)
    )

    array_ndims = Property(Self.designated_type.then(
        # "designated_type" may return no node for incorrect code
        lambda t: t.array_ndims,
        default_val=Literal(0)
    ))
    defining_env = Property(Self.designated_type.defining_env)


@abstract
class AccessExpression(TypeExprVariant):
    array_ndims = Property(Literal(0))
    # TODO? Should we handle defining_env here for implicit dereferencing?


class SubprogramAccessExpression(AccessExpression):
    is_protected = Field(repr=False)
    subp_spec = Field()


class TypeAccessExpression(AccessExpression):
    is_all = Field()
    is_constant = Field()
    subtype_name = Field()


class ParameterProfile(AdaNode):
    ids = Field()
    is_aliased = Field()
    mode = Field()
    type_expr = Field()
    default = Field()
    is_mandatory = Property(Self.default.is_null)

    env_spec = EnvSpec(add_to_env=(symbol_list(Self.ids), Self))


class AspectSpecification(AdaNode):
    aspect_assocs = Field()


class BasicSubprogramDecl(BasicDecl):
    _macros = [child_unit(Self.subp_spec.name.name.symbol,
                          Self.subp_spec.name.scope,
                          Self)]

    is_overriding = Field()
    subp_spec = Field()

    name = Property(Self.subp_spec.name)
    defining_names = Property(Self.subp_spec.name.singleton)
    defining_env = Property(Self.subp_spec.defining_env)


class SubprogramDecl(BasicSubprogramDecl):
    aspects = Field()


class NullSubprogramDecl(BasicSubprogramDecl):
    aspects = Field()


class AbstractSubprogramDecl(BasicSubprogramDecl):
    aspects = Field()


class ExpressionFunction(BasicSubprogramDecl):
    expression = Field()
    aspects = Field()


class RenamingSubprogramDecl(BasicSubprogramDecl):
    renames = Field()
    aspects = Field()


class Pragma(AdaNode):
    id = Field()
    args = Field()


class PragmaArgument(AdaNode):
    id = Field()
    expr = Field()


######################
# GRAMMAR DEFINITION #
######################

class InOut(EnumType):
    alternatives = ["in", "out", "inout"]
    suffix = 'way'


@abstract
class AspectClause(AdaNode):
    pass


class EnumRepClause(AspectClause):
    type_name = Field()
    aggregate = Field()


class AttributeDefClause(AspectClause):
    attribute_expr = Field()
    expr = Field()


class RecordRepComponent(AdaNode):
    id = Field()
    position = Field()
    range = Field()


class RecordRepClause(AspectClause):
    component_name = Field()
    at_expr = Field()
    components = Field()


class AtClause(AspectClause):
    name = Field()
    expr = Field()


class EntryDecl(BasicDecl):
    overriding = Field()
    entry_id = Field()
    family_type = Field()
    params = Field()
    aspects = Field()

    defining_names = Property(Self.entry_id.cast(T.Name).singleton)


class TaskDecl(BasicDecl):
    task_name = Field()
    aspects = Field()
    definition = Field()

    defining_names = Property(Self.task_name.cast(T.Name).singleton)


class ProtectedDecl(BasicDecl):
    protected_name = Field()
    aspects = Field()
    definition = Field()

    defining_names = Property(Self.protected_name.cast(T.Name).singleton)


class AspectAssoc(AdaNode):
    id = Field()
    expr = Field()


class NumberDecl(BasicDecl):
    ids = Field()
    expr = Field()

    defining_names = Property(Self.ids.map(lambda id: id.cast(T.Name)))


class ObjectDecl(BasicDecl):
    ids = Field()
    aliased = Field()
    constant = Field()
    inout = Field()
    type_expr = Field()
    default_expr = Field()
    renaming_clause = Field()
    aspects = Field()

    env_spec = EnvSpec(add_to_env=(symbol_list(Self.ids), Self))

    array_ndims = Property(
        # The grammar says that the "type" field can be only a TypeExpression
        # or an ArrayTypeDef, so we have a bug somewhere if we get anything
        # else.
        Self.type_expr.cast(ArrayTypeDef).then(
            lambda array_type: array_type.array_ndims,
            default_val=(
                Self.type_expr.cast_or_raise(TypeExpression).array_ndims
            )
        ),
    )
    defining_names = Property(Self.ids.map(lambda id: id.cast(T.Name)))
    defining_env = Property(
        Self.type_expr.cast(TypeExpression).then(
            lambda te: te.defining_env,
            default_val=EmptyEnv
        )
    )


class PrivatePart(AdaNode):
    decls = Field()
    env_spec = EnvSpec(add_env=True)


class BasePackageDecl(BasicDecl):
    """
    Package declarations. Concrete instances of this class
    will be created in generic package declarations. Other non-generic
    package declarations will be instances of PackageDecl.

    The behavior is the same, the only difference is that BasePackageDecl
    and PackageDecl have different behavior regarding lexical environments.
    In the case of generic package declarations, we use BasePackageDecl
    which has no env_spec, and the environment behavior is handled by the
    GenericPackageDecl instance.
    """
    package_name = Field()
    aspects = Field()
    decls = Field()
    private_part = Field()
    end_id = Field()

    name = Property(Self.package_name, private=True)
    defining_names = Property(Self.name.singleton)
    defining_env = Property(Self.children_env.env_orphan)


class PackageDecl(BasePackageDecl):
    """
    Non-generic package declarations.
    """
    _macros = [child_unit(Self.package_name.name.symbol,
                          Self.package_name.scope)]


class ExceptionDecl(BasicDecl):
    """
    Exception declarations.
    """
    ids = Field()
    renames = Field()
    aspects = Field()
    defining_names = Property(Self.ids.map(lambda id: id.cast(T.Name)))


@abstract
class GenericInstantiation(BasicDecl):
    """
    Instantiations of generics.
    """
    name = Field()
    generic_entity_name = Field()
    parameters = Field()
    aspects = Field()
    defining_names = Property(Self.name.singleton)


class GenericProcedureInstantiation(GenericInstantiation):
    pass


class GenericFunctionInstantiation(GenericInstantiation):
    pass


class GenericPackageInstantiation(GenericInstantiation):
    pass


class RenamingClause(AdaNode):
    """
    Renaming clause, used everywhere renamings are valid.
    """
    renamed_object = Field()


class PackageRenamingDecl(BasicDecl):
    name = Field()
    renames = Field(type=RenamingClause)
    aspects = Field()

    defining_names = Property(Self.name.singleton)


class GenericRenamingDecl(BasicDecl):
    name = Field()
    renames = Field()
    aspects = Field()

    defining_names = Property(Self.name.singleton)


class FormalSubpDecl(BasicDecl):
    """
    Formal subprogram declarations, in generic declarations formal parts.
    """
    subp_spec = Field()
    is_abstract = Field()
    default_value = Field()
    aspects = Field()

    defining_names = Property(Self.subp_spec.name.singleton)


class Overriding(EnumType):
    alternatives = ["overriding", "not_overriding", "unspecified"]
    suffix = 'kind'


class GenericSubprogramDecl(BasicDecl):
    formal_part = Field()
    subp_spec = Field()
    aspects = Field()

    defining_names = Property(Self.subp_spec.name.singleton)


class GenericPackageDecl(BasicDecl):
    _macros = [child_unit(Self.package_name.name.symbol,
                          Self.package_name.scope)]

    formal_part = Field()
    package_decl = Field(type=BasePackageDecl)

    package_name = Property(Self.package_decl.package_name)

    defining_names = Property(Self.package_name.singleton)


def is_package(e):
    """
    Property helper to determine if an entity is a package or not.

    TODO: This current solution is not really viable, because:
    1. Having to do local imports of AdaNode subclasses is tedious.
    2. is_package could be useful in other files.

    This probably hints towards a reorganization of the types definition.

    :type e: AbstractExpression
    :rtype: AbstractExpression
    """
    return e.is_a(PackageDecl, PackageBody)


@abstract
class Expr(AdaNode):
    designated_env = AbstractProperty(
        type=compiled_types.LexicalEnvType, private=True, runtime_check=True,
        doc="""
        Returns the lexical environment designated by this name.

        If this name involves overloading, this will return a combination of
        the various candidate lexical environments.
        """
    )

    scope = AbstractProperty(
        type=compiled_types.LexicalEnvType, private=True, runtime_check=True,
        doc="""
        Returns the lexical environment that is the scope in which the
        entity designated by this name is defined/used.
        """
    )

    name = AbstractProperty(
        type=compiled_types.Token, private=True, runtime_check=True,
        doc="""
        Returns the relative name of this instance. For example,
        for a prefix A.B.C, this will return C.
        """
    )

    env_elements = AbstractProperty(
        type=compiled_types.EnvElement.array_type(), runtime_check=True,
        doc="""
        Returns the list of annotated elements in the lexical environment
        that can statically be a match for expr before overloading analysis.
        """
    )

    entities = Property(
        Self.env_elements.map(lambda e: e.el), type=AdaNode.array_type(),
        doc="""
        Same as env_elements, but return bare AdaNode instances rather than
        EnvElement instances.
        """
    )

    designated_type = AbstractProperty(
        type=TypeDecl, runtime_check=True,
        doc="""
        Assuming this expression designates a type, return this type.

        Since in Ada this can be resolved locally without any non-local
        analysis, this doesn't use logic equations.
        """
    )


class UnOp(Expr):
    op = Field()
    expr = Field()


class BinOp(Expr):
    left = Field()
    op = Field()
    right = Field()


class MembershipExpr(Expr):
    expr = Field()
    op = Field()
    membership_exprs = Field()


class Aggregate(Expr):
    ancestor_expr = Field()
    assocs = Field()


class CallExpr(Expr):
    name = Field()
    suffix = Field()

    designated_env = Property(
        Self.entities().map(lambda e: e.match(
            lambda subp=BasicSubprogramDecl: subp.defining_env,
            lambda subp=SubprogramBody:      subp.defining_env,
            lambda others:                   EmptyEnv,
        )).env_group
    )

    env_elements = Property(Self.name.env_elements)

    # CallExpr can appear in type expressions: they are used to create implicit
    # subtypes for discriminated records or arrays.
    designated_type = Property(Self.name.designated_type)


class ParamAssoc(AdaNode):
    designator = Field()
    expr = Field()


class ParamList(AdaNode):
    params = Field()


class AccessDeref(Expr):
    pass


class DiamondExpr(Expr):
    pass


class OthersDesignator(AdaNode):
    pass


class AggregateMember(AdaNode):
    choice_list = Field()


class Op(EnumType):
    """Operation in a binary expression."""
    alternatives = ["and", "or", "or_else", "and_then", "xor", "in",
                    "not_in", "abs", "not", "pow", "mult", "div", "mod",
                    "rem", "plus", "minus", "bin_and", "eq", "neq", "lt",
                    "lte", "gt", "gte", "ellipsis"]
    suffix = 'op'


class IfExpr(Expr):
    cond_expr = Field()
    then_expr = Field()
    elsif_list = Field()
    else_expr = Field()


class ElsifExprPart(AdaNode):
    cond_expr = Field()
    then_expr = Field()


class CaseExpr(Expr):
    expr = Field()
    cases = Field()


class CaseExprAlternative(Expr):
    choices = Field()
    expr = Field()


@abstract
class Name(Expr):

    env_for_scope = Property(
        EmptyEnv,
        doc="""
        Lexical environment this identifier represents. This is similar to
        designated_env although it handles only cases for child units and it is
        used only during the environment population pass so it does not return
        orphan environments.
        """
    )


@abstract
class SingleTokNode(Name):
    tok = Field()

    name = Property(Self.tok)

    @langkit_property(return_type=BoolType)
    def matches(other=T.SingleTokNode):
        """
        Return whether this token and the "other" one are the same.
        This is only defined for two nodes that wrap symbols.

        """
        return Self.name.symbol == other.name.symbol


class BaseId(SingleTokNode):

    env_for_scope = Property(Env.resolve_unique(Self.tok).el.match(
        lambda decl=T.PackageDecl: decl.children_env,
        lambda body=T.PackageBody: body.children_env,
        lambda others:             EmptyEnv
    ))

    designated_env = Property(
        Self.entities.map(lambda el: el.cast(BasicDecl).then(
            lambda decl: decl.defining_env
        )).env_group
    )

    scope = Property(Env)
    name = Property(Self.tok)

    # This implementation of designated_type is more permissive than the
    # "legal" one since it will skip entities that are eventually available
    # first in the env, shadowing the actual type, if they are not types. It
    # will allow to get working XRefs in simple shadowing cases.
    designated_type = Property(
        Self.entities.map(lambda e: e.cast(TypeDecl)).filter(lambda e: (
            Not(e.is_null)
        )).at(0)
    )

    @langkit_property(return_type=CallExpr)
    def parent_callexpr():
        """
        If this BaseId is the main symbol qualifying the prefix in a call
        expression, this returns the corresponding CallExpr node. Return null
        otherwise. For example::

            C (12, 15);
            ^ parent_callexpr = <CallExpr>

            A.B.C (12, 15);
                ^ parent_callexpr = <CallExpr>

            A.B.C (12, 15);
              ^ parent_callexpr = null

            C (12, 15);
               ^ parent_callexpr = null
        """
        return Self.parents.take_while(lambda p: Or(
            p.is_a(CallExpr),
            p.is_a(Prefix, BaseId) & p.parent.match(
                lambda pfx=Prefix: pfx.suffix == p,
                lambda ce=CallExpr: ce.name == p,
                lambda _: False
            )
        )).find(lambda p: p.is_a(CallExpr)).cast(CallExpr)

    @langkit_property()
    def env_elements():
        items = Var(Env.get(Self.tok))
        pc = Var(Self.parent_callexpr)

        return If(
            pc.is_null,

            # If it is not the main id in a CallExpr: either the name
            # designates something else than a subprogram, either it designates
            # a subprogram that accepts no explicit argument. So filter out
            # other subprograms.
            items.filter(lambda e: e.el.match(
                lambda decl=BasicDecl: Let(
                    lambda subp_spec=decl.match(
                        lambda subp=BasicSubprogramDecl: subp.subp_spec,
                        lambda subp=SubprogramBody:      subp.subp_spec,
                        lambda others: No(SubprogramSpec),
                    ): (
                        subp_spec.then(lambda ss: (
                            (e.MD.dottable_subprogram
                                & (ss.nb_min_params == 1))
                            | (ss.nb_min_params == 0)
                        ), default_val=True)
                    )
                ),
                lambda others: True,
            )),

            # This identifier is the name for a called subprogram or an array.
            # So only keep:
            # * subprograms for which the actuals match;
            # * arrays for which the number of dimensions match.
            pc.suffix.cast(ParamList).then(lambda params: (
                items.filter(lambda e: e.el.match(
                    lambda subp=BasicSubprogramDecl:
                        subp.subp_spec.is_matching_param_list(params),
                    lambda subp=SubprogramBody:
                        subp.subp_spec.is_matching_param_list(params),
                    lambda o=ObjectDecl: o.array_ndims == params.params.length,
                    lambda _: True
                ))
            ), default_val=items)
        )

    # TODO: For the moment this is just binding the reference variable. We also
    # want to bind the type variable to the corresponding entities's types, and
    # bind them together two by two.
    xref_equation = Property(
        Domain(Self.ref_var, Self.entities),
        doc="TODO: Add doc when this property will have a base property",
        private=True
    )


class Identifier(BaseId):
    _repr_name = "Id"


class StringLiteral(BaseId):
    _repr_name = "Str"


class EnumIdentifier(Identifier):
    _repr_name = "EnumId"


class CharLiteral(BaseId):
    _repr_name = "Chr"


class NumLiteral(SingleTokNode):
    _repr_name = "Num"


class NullLiteral(SingleTokNode):
    _repr_name = "Null"


class Attribute(SingleTokNode):
    _repr_name = "Attr"


class SingleParameter(Struct):
    name = Field(type=Identifier)
    profile = Field(type=ParameterProfile)


class ParamMatch(Struct):
    """
    Helper data structure to implement SubprogramSpec/ParamAssocList matching.

    Each value relates to one ParamAssoc.
    """
    has_matched = Field(type=BoolType, doc="""
        Whether the matched ParamAssoc a ParameterProfile.
    """)
    is_formal_opt = Field(type=BoolType, doc="""
        Whether the matched ParameterProfile has a default value (and is thus
        optional).
    """)


class SubprogramSpec(AdaNode):
    name = Field()
    params = Field()
    returns = Field()

    typed_param_list = Property(
        Self.params.mapcat(
            lambda profile: profile.ids.map(lambda id: (
                New(SingleParameter, name=id, profile=profile)
            ))
        ),
        doc='Collection of couples (identifier, param profile) for all'
            ' parameters'
    )

    nb_min_params = Property(
        Self.typed_param_list.filter(lambda p: p.profile.is_mandatory).length,
        type=LongType, doc="""
        Return the minimum number of parameters this subprogram can be called
        while still being a legal call.
        """
    )

    nb_max_params = Property(
        Self.typed_param_list.length, type=LongType,
        doc="""
        Return the maximum number of parameters this subprogram can be called
        while still being a legal call.
        """
    )

    @langkit_property(return_type=ParamMatch.array_type())
    def match_param_list(params=ParamList):
        """
        For each ParamAssoc in a ParamList, return whether we could find a
        matching formal in this SubprogramSpec and whether this formal is
        optional (i.e. has a default value).
        """
        typed_params = Var(Self.typed_param_list)
        no_match = Var(New(ParamMatch, has_matched=False, is_formal_opt=False))

        return params.params.map(lambda i, pa: If(
            pa.designator.is_null,

            # Positional parameter case: if this parameter has no
            # name association, make sure we have enough formals.
            typed_params.at(i).then(lambda single_param: New(
                ParamMatch,
                has_matched=True,
                is_formal_opt=Not(single_param.profile.default.is_null)
            ), no_match),

            # Named parameter case: make sure the designator is
            # actualy a name and that there is a corresponding
            # formal.
            pa.designator.cast(Identifier).then(lambda id: (
                typed_params.find(lambda p: p.name.matches(id)).then(
                    lambda p: New(
                        ParamMatch,
                        has_matched=True,
                        is_formal_opt=Not(p.profile.default.is_null)
                    ), no_match
                )
            ), no_match)
        ))

    @langkit_property(return_type=BoolType)
    def is_matching_param_list(params=ParamList):
        """
        Return whether a ParamList is a match for this SubprogramSpec, i.e.
        whether the argument count (and designators, if any) match.
        """
        match_list = Var(Self.match_param_list(params))

        return And(
            params.params.length <= Self.nb_max_params,
            match_list.all(lambda m: m.has_matched),
            match_list.filter(
                lambda m: Not(m.is_formal_opt)
            ).length == Self.nb_min_params,
        )

    @langkit_property(return_type=BoolType)
    def match_param_assoc(pa=ParamAssoc):
        """
        Return whether some parameter association matches an argument in this
        subprogram specification. Note that this matching disregards types: it
        only considers arity and designators (named parameters).
        """
        # Parameter associations can match only if there is at least one
        # formal in this spec.
        return (Self.nb_max_params > 0) & (
            # Then, all associations with no designator match, as we don't
            # consider types.
            Not(pa.designator.is_null)

            # The ones with a designator match iff the designator is an
            # identifier whose name is present in the list of formals.
            | pa.designator.cast(Identifier).then(
                lambda id: Self.typed_param_list.any(
                    lambda p: p.name.matches(id)
                )
            )
        )

    @langkit_property(return_type=compiled_types.LexicalEnvType, private=True)
    def defining_env():
        """
        Helper for BasicDecl.defining_env.
        """
        return If(Self.returns.is_null,
                  EmptyEnv,
                  Self.returns.defining_env)


class Quantifier(EnumType):
    alternatives = ["all", "some"]
    suffix = 'items'


class IterType(EnumType):
    alternatives = ["in", "of"]
    suffix = 'iter'


@abstract
class LoopSpec(AdaNode):
    pass


class ForLoopSpec(LoopSpec):
    id = Field()
    loop_type = Field()
    is_reverse = Field()
    iter_expr = Field()


class QuantifiedExpr(Expr):
    quantifier = Field()
    loop_spec = Field()
    expr = Field()


class Allocator(Expr):
    subpool = Field()
    expr = Field()


class QualExpr(Expr):
    prefix = Field()
    suffix = Field()


@abstract
class AbstractAggregateContent(AdaNode):
    pass


class AggregateContent(AbstractAggregateContent):
    fields = Field()


class AggregateAssoc(AdaNode):
    designator = Field()
    expr = Field()


class AttributeRef(Expr):
    prefix = Field()
    attribute = Field()
    args = Field()

    designated_type = Property(Self.prefix.designated_type)


class RaiseExpression(Expr):
    exception_name = Field()
    error_message = Field()


class Prefix(Name):
    prefix = Field()
    suffix = Field()

    designated_env = Property(
        Self.prefix.designated_env.eval_in_env(Self.suffix.designated_env)
    )

    env_for_scope = Property(Self.suffix.cast(BaseId).then(
        lambda sfx: Self.scope.eval_in_env(sfx.env_for_scope),
        default_val=EmptyEnv
    ))

    scope = Property(Self.prefix.match(
        lambda name=T.Name: name.env_for_scope,
        lambda others:      EmptyEnv
    ))

    name = Property(Self.suffix.name)

    env_elements = Property(
        Self.prefix.designated_env.eval_in_env(Self.suffix.env_elements)
    )

    # This implementation of designated_type is more permissive than the
    # "legal" one since it will skip entities that are eventually available
    # first in the env if they are not packages.
    designated_type = Property(lambda: (
        Self.prefix.entities.filter(is_package).at(0).children_env.eval_in_env(
            Self.suffix.designated_type
        )
    ))


class CompilationUnit(AdaNode):
    """Root node for all Ada analysis units."""
    prelude = Field(doc="``with``, ``use`` or ``pragma`` statements.")
    bodies = Field()

    env_spec = EnvSpec(add_env=True)


class SubprogramBody(Body):
    _macros = [child_unit(Self.subp_spec.name.name.symbol,
                          Self.subp_spec.name.scope,
                          Self)]

    overriding = Field()
    subp_spec = Field()
    aspects = Field()
    decls = Field()
    statements = Field()
    end_id = Field()

    defining_names = Property(Self.subp_spec.name.singleton)
    defining_env = Property(Self.subp_spec.defining_env)


class HandledStatements(AdaNode):
    statements = Field()
    exceptions = Field()


class ExceptionHandler(AdaNode):
    exc_name = Field()
    catched_exceptions = Field()
    statements = Field()


@abstract
class Statement(AdaNode):
    pass


class CallStatement(Statement):
    call = Field()


class NullStatement(Statement):
    null_lit = Field(repr=False)


class AssignStatement(Statement):
    dest = Field()
    expr = Field()


class GotoStatement(Statement):
    label_name = Field()


class ExitStatement(Statement):
    loop_name = Field()
    condition = Field()


class ReturnStatement(Statement):
    return_expr = Field()


class RequeueStatement(Statement):
    call_name = Field()
    with_abort = Field()


class AbortStatement(Statement):
    names = Field()


class DelayStatement(Statement):
    until = Field()
    expr = Field()


class RaiseStatement(Statement):
    exception_name = Field()
    error_message = Field()


class IfStatement(Statement):
    condition = Field()
    statements = Field()
    alternatives = Field()
    else_statements = Field()


class ElsifStatementPart(AdaNode):
    expr = Field()
    statements = Field()


class Label(Statement):
    token = Field()


class WhileLoopSpec(LoopSpec):
    expr = Field()


class LoopStatement(Statement):
    name = Field()
    spec = Field()
    statements = Field()


class BlockStatement(Statement):
    name = Field()
    decls = Field()
    statements = Field()

    env_spec = EnvSpec(add_env=True)


class ExtReturnStatement(AdaNode):
    object_decl = Field()
    statements = Field()


class CaseStatement(Statement):
    case_expr = Field()
    case_alts = Field()


class CaseStatementAlternative(AdaNode):
    choices = Field()
    statements = Field()


class AcceptStatement(Statement):
    name = Field()
    entry_index_expr = Field()
    parameters = Field()
    statements = Field()


class SelectStatement(Statement):
    guards = Field()
    else_statements = Field()
    abort_statements = Field()


class SelectWhenPart(Statement):
    choices = Field()
    statements = Field()


class TerminateStatement(Statement):
    pass


class PackageBody(Body):
    _macros = [child_unit(Self.package_name.name.symbol,
                          Self.package_name.scope)]

    package_name = Field()
    aspects = Field()
    decls = Field()
    statements = Field()

    defining_names = Property(Self.package_name.singleton)
    defining_env = Property(Self.children_env.env_orphan)


class TaskBody(Body):
    package_name = Field()
    aspects = Field()
    decls = Field()
    statements = Field()

    defining_names = Property(Self.package_name.singleton)


class ProtectedBody(Body):
    package_name = Field()
    aspects = Field()
    decls = Field()

    defining_names = Property(Self.package_name.singleton)


class EntryBody(Body):
    entry_name = Field()
    index_spec = Field()
    parameters = Field()
    when_cond = Field()
    decls = Field()
    statements = Field()

    defining_names = Property(Self.entry_name.cast(Name).singleton)


class EntryIndexSpec(AdaNode):
    id = Field()
    subtype = Field()


class Subunit(AdaNode):
    name = Field()
    body = Field()


class ProtectedBodyStub(BodyStub):
    name = Field()
    aspects = Field()

    defining_names = Property(Self.name.singleton)


class SubprogramBodyStub(BodyStub):
    overriding = Field()
    subp_spec = Field()
    aspects = Field()

    defining_names = Property(Self.subp_spec.name.singleton)
    # Note that we don't have to override the defining_env property here since
    # what we put in lexical environment is their SubprogramSpec child.


class PackageBodyStub(BodyStub):
    name = Field()
    aspects = Field()

    defining_names = Property(Self.name.singleton)


class TaskBodyStub(BodyStub):
    name = Field()
    aspects = Field()

    defining_names = Property(Self.name.singleton)


class LibraryItem(AdaNode):
    is_private = Field()
    item = Field()
