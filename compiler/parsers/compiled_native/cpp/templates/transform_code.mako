## vim: filetype=cpp

${code}
% if _self.get_type().is_ptr:
    ${res} = ${_self.typ.nullexpr()};
% endif

if (${cpos} != -1) {
    % if _self.parser.needs_refcount() and not is_row(_self.parser):
        if (${cres}) ${cres}->inc_ref();
    % endif

    % if _self.get_type().is_ptr:
        ${res} = ${_self.typ.name()}_new();
    % endif

    % for f, arg in zip(_self.typ.get_fields(), args):
        ${res}${"->" if _self.get_type().is_ptr else "."}${f.name} = ${arg}; 
    % endfor
}
