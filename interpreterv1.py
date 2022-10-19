from intbase import InterpreterBase, ErrorType
import shlex
import re
from os import abort

class Interpreter(InterpreterBase):
  NUMBER_REGEX = "-[1-9][0-9]*$|[0-9]$|[1-9][0-9]*$"
  OPERATORS = {"+", "-", "*", "/", "%", "<", ">", "<=", ">=", "!=", "==", "&", "|"}
  def __init__(self, console_output=True, input=None, trace_output=False):
    super().__init__(console_output, input)
    self.variables = {}
    self.operand_stk = []
    self.operator_stk = []
    self.indentation_stk = []
    
  def run(self, program):
    super().validate_program(program)
    # TODO: check when no main exists
    self.program = program
    self.ip_ = self.find_main()
    terminated = False
    
    while (not terminated):
      self.__interpret()
  
  def find_main(self):
    for line in range(len(self.program)):
      if line == "func main":
        return line
    return -1
  
  def tokenize(self, line):
    tokens_with_comments = shlex.split(line)
    tokens = []
    for token in tokens_with_comments:
      if (len(token) > 0 and token[0] == '#'):
        break
      else:
        tokens.append(token)
    return tokens
    
  def interpret(self):
    # parse current line into tokens
    line = self.program[self.ip_]
    
    # nothing to process on current line, move to next line
    tokens = self.tokenize(line)
    if (len(tokens) == 0):
      self.ip_ += 1
      return
    
    # determine whitespace offset
    i = 0
    while (i < len(line) and line[i] == ' '):
      i+=1
    self.indentation_stk.append(i)
    
    token = tokens[0]
    if (token == self.FUNC_DEF):
      self.process_func()
    elif (token == self.ENDFUNC_DEF):
      self.process_endfunc()
    elif (token == self.WHILE_DEF):
      self.process_while()
    elif (token == self.ELSE_DEF):
      self.process_else()
    elif (token == self.ENDIF_DEF):
      self.process_endif()
    elif (token == self.ASSIGN_DEF):
      self.process_assign()
    elif (token == self.FUNCCALL_DEF):
      self.process_funccall()
    elif (token == self.IF_DEF):
      self.process_if()
    elif (token == self.RETURN_DEF):
      self.process_return()
    
  def process_assign(self, tokens):
    if (len(tokens) < 3):
      # TODO: implement error handling
      abort()
    var_name = tokens[1]
    if (re.match("[a-zA-Z][a-zA-z0-9_]*$", var_name)) is None:
      self.error(ErrorType.SYNTAX_ERROR, description="variables names must begin with letters and consist of letters, numbers, and underscores.")
    if (len(tokens) == 3):
        var_val = self.process_variable(tokens[2])
    else:
      var_val = self.process_expression(tokens[2:])
    
    self.variables[var_name] = var_val
    
  def process_variable(self, v):
    if (re.match(self.NUMBER_REGEX, v)):
      return int(v)
    elif (v in self.variables):
      return self.variables[v]
    elif (re.match("\".*\"", v)):
      return v[1:-1]
    elif (v == 'True'):
      return True
    elif (v == 'False'):
      return False
    else:
      self.error(ErrorType.NAME_ERROR, description=f"variable {v} is not defined")
    
  def process_expression(self, tokens):
    for token in tokens:
      if token in self.OPERATORS:
        self.operator_stk.append(token)
      else:
        self.operand_stk.append(self.process_variable(token))
        
    while (self.operator_stk and len(self.operand_stk) >= 2):
      op = self.operator_stk.pop()
      b = self.operand_stk.pop()
      a = self.operand_stk.pop()
      res = self.compute(op, a, b)
      self.operand_stk.append(res)
    
    if (self.operator_stk or len(self.operand_stk) > 1):
      self.error(ErrorType.SYNTAX_ERROR, description="improper expression syntax")
    
    return self.operand_stk.pop()
    
  def compute(self, op, a, b):
    if not isinstance(a, type(b)) and not isinstance(b, type(a)):
      self.error(ErrorType.TYPE_ERROR, description=f"mismatched types '{type(a)}' and '{type(b)}'")
      
    if op == '==':
      return a == b
    elif op == '!=':
      return a != b
    
    if isinstance(a, int) and not isinstance(a, bool) or isinstance(a, str):
      if op == '+':
        return a+b
      elif op == '<':
        return a < b
      elif op == '>':
        return a > b
      elif op == '<=':
        return a <= b
      elif op == '>=':
        return a >= b
      
    if isinstance(a, int) and not isinstance(a, bool):
      if op == '-':
        return a-b
      elif op == '*':
        return a*b
      elif op == '/':
        return a//b
      elif op == '%':
        return a % b
      
    if isinstance(a, bool):
      if op == '&':
        return a and b
      elif op == '|':
        return a or b
  
    return self.error(ErrorType.TYPE_ERROR, description=f"operands of type '{type(a)}' incompatible with operator '{op}'")
      
      
      
      