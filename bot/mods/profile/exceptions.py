from lamb.exceptions import ModException


class GroupsException(ModException):
    pass


class PermitNotExistsError(GroupsException):
    msg = 'Permit <{}> does not exists'


class GroupTypeNotExistsError(GroupsException):
    msg = 'Group type <{}> does not exists'


class GroupNotExistsError(GroupsException):
    msg = 'Group <{}> does not exists'


class TripcodeRequirementError(GroupsException):
    msg = 'User <{}> must have tripcode to add to <{}> group'
