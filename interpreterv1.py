from intbase import InterpreterBase, ErrorType
import re

class Interpreter(InterpreterBase):
  NAME_REGEX = "[a-zA-Z][a-zA-z0-9_]*$"
  NUMBER_REGEX = "-[1-9][0-9]*$|[0-9]$|[1-9][0-9]*$"
  OPERATORS = {"+", "-", "*", "/", "%", "<", ">", "<=", ">=", "!=", "==", "&", "|"}
  TYPE_IDX = 0
  INDENT_IDX = 1
  INFO_IDX = 2
  WHILE_IP = 0
  AFTER_ENDWHILE_IP = 1
  FUNCTION_NAME = 0
  AFTER_FUNCCALL_IP = 1
  def __init__(self, console_output=True, input=None, trace_output=False):
    super().__init__(console_output, input)
    self.variables = {}
    self.functions = {}
    self.operand_stk = []
    self.operator_stk = []
    self.indents = [] # stores indents for each line
    self.tokenized_lines = [] # stores tokenized version of each line
    self.block_stk = [] # 4 fields: type (funccall, if, while), ip, indent, specific info based on type
    self.terminated = False
    self.ip_ = 0
    
  def run(self, program):
    super().validate_program(program)
    # TODO: check when no main exists
    self.program = program
    
    # tokenize everything and calculate indentations at beginning
    for line in self.program:
      self.indents.append(self.calculate_indent(line))
      self.tokenized_lines.append(self.tokenize(line))
      
    # find all function definitions and move ip to main function 
    self.find_funcs_and_main()
    
    while (not self.terminated):
      self.__interpret()
  
  def find_funcs_and_main(self):
    for i in range(len(self.tokenized_lines)):
      tokens = self.tokenized_lines[i]
      if (len(tokens) < 2):
        continue
      if tokens[0] == self.FUNC_DEF:
        self.initialize_func(tokens, i)
      
  def initialize_func(self, tokens, i):
    if (len(tokens) < 2):
      self.error(ErrorType.SYNTAX_ERROR, description=f"invalid number of arguments for func, need 2, got {len(tokens)}", line_num=i)
    func_name = tokens[1]
    self.functions[func_name] = i
    # main function is an exception in that func instead of funccall representing invocation
    if func_name == "main":
      self.ip_ = i+1
      self.block_stk.append([self.FUNCCALL_DEF, self.indents[i], [func_name, None]])
      return

  def calculate_indent(self, line):
    indent = 0
    while (indent < len(line) and line[indent] == ' '):
      indent+=1
    return indent
  
  def tokenize(self, line):
    # regex found at https://stackoverflow.com/questions/16710076/python-split-a-string-respect-and-preserve-quotes
    tokens_with_comments = re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', line)
    tokens = []
    # iterate through tokens and break at first '#' not in a comment, thus ignoring all subsequent tokens (comments)
    for token in tokens_with_comments:
      commentBegin = token.find("#")
      if commentBegin == 0:
        break
      # 2 quotes before comment indicates string, 0 quotes before comment
      # indicates other token, we need to keep token in both cases
      elif commentBegin > 0 and token[:commentBegin].count('\"') % 2 == 0:
        tokens.append(token[:commentBegin])
        break
      else:
        tokens.append(token)
    return tokens
    
  def __interpret(self):
    # parse current line into tokens
    tokens = self.tokenized_lines[self.ip_]
    
    # nothing to process on current line, move to next line
    if (len(tokens) == 0):
      self.ip_ += 1
      return
    
    token = tokens[0]
    if (token == self.FUNC_DEF):
      self.process_func()
    if (token == self.FUNCCALL_DEF):
      self.process_funccall(tokens)
    elif (token == self.RETURN_DEF):
      self.process_return(tokens)
    elif (token == self.ENDFUNC_DEF):
      self.process_endfunc(tokens)
    elif (token == self.STRTOINT_DEF):
      self.process_strtoint(tokens)
    elif (token == self.INPUT_DEF):
      self.process_input(tokens)
    elif (token == self.PRINT_DEF):
      self.process_print(tokens)
    elif (token == self.IF_DEF):
      self.process_if(tokens)
    elif (token == self.ELSE_DEF):
      self.process_else(tokens)
    elif (token == self.ENDIF_DEF):
      self.process_endif(tokens)
    elif (token == self.WHILE_DEF):
      self.process_while(tokens)
    elif (token == self.ENDWHILE_DEF):
      self.process_endwhile(tokens)
    elif (token == self.ASSIGN_DEF):
      self.process_assign(tokens)
    
  def process_func(self):
    # since we prepross all functions, encountering a func during interpretation
    # should just move ip to first actual line of function
    self.ip_+=1
      
  def process_funccall(self, tokens):
    if (len(tokens) < 2):
      self.error(ErrorType.SYNTAX_ERROR, description=f"invalid number of arguments for funccall, need 2, got {len(tokens)}", line_num=self.ip_)
      
    # check that indent is greater than outer block
    if not self.block_stk or self.block_stk[-1][self.INDENT_IDX] >= self.indents[self.ip_]:
      self.error(ErrorType.SYNTAX_ERROR, description="misaligned funccall statement", line_num=self.ip_)
    
    func_name = tokens[1]
    # handle calling prefined functions
    if func_name == self.STRTOINT_DEF:
        self.process_strtoint(tokens)
        return
    elif func_name == self.INPUT_DEF:
        self.process_input(tokens)
        return
    elif func_name == self.PRINT_DEF:
        self.process_print(tokens)
        return
        
    # validate func_name if it did not match predefined functions
    if func_name not in self.functions:
      self.error(ErrorType.NAME_ERROR, description=f"function {func_name} is not defined", line_num=self.ip_)
    
    loc = self.functions[func_name]
    
    # push funccall statement to block_stk since new block has been created
    # (did not need this for predefined functions since we can guarantee no further block nesting)
    self.block_stk.append([self.FUNCCALL_DEF, self.indents[loc], [func_name, self.ip_+1]])
        
    #  move ip to function definition 
    self.ip_ = loc
  
  def process_return(self, tokens):
    # hitting return still moves ip to endfunc for generalized approach with an without return statement
    if (len(tokens) >= 2):
      expr_res = self.process_expression(tokens[1:])
      self.variables["result"] = expr_res
      
    # pop from block_stk until reaching innermost funccall (since return could be inside another block)
    while self.block_stk and self.block_stk[-1][self.TYPE_IDX] != self.FUNCCALL_DEF:
      self.block_stk.pop()
      
    # find endfunc for current function (since we want to exit this function)
    for i in range(self.ip_+1, len(self.program)):
      if self.indents[i] == self.block_stk[-1][self.INDENT_IDX] and len(self.tokenized_lines[i]) >= 1 and self.tokenized_lines[i][0] == self.ENDFUNC_DEF:
        self.ip_ = i
        break
  
  def process_endfunc(self, tokens):
    if (len(tokens) != 1):
      self.error(ErrorType.SYNTAX_ERROR, description=f"endfunc may not be followed by an expression", line_num=self.ip_)
      
    # check that innermost open block is a funccall with same indent
    if not self.block_stk or self.block_stk[-1][self.TYPE_IDX] != self.FUNCCALL_DEF or self.block_stk[-1][self.INDENT_IDX] != self.indents[self.ip_]:
      self.error(ErrorType.SYNTAX_ERROR, description="mismatched endfunc statement")
    
    # terminate program if reaching end of execution for main
    if self.block_stk[-1][self.INFO_IDX][self.FUNCTION_NAME] == "main":
      self.terminated = True
      
    next_ip = self.block_stk[-1][self.INFO_IDX][self.AFTER_FUNCCALL_IP] # save next location of ip before popping
    self.block_stk.pop() # pop current block
    self.ip_ = next_ip
    
  def process_strtoint(self, tokens):
    # check if 3 arguments
    if (len(tokens) != 3):
      self.error(ErrorType.SYNTAX_ERROR, description=f"invalid number of arguments for funccall strtoint, need 3, got {len(tokens)}", line_num=self.ip_)
      
    # num_str is string to convert
    num_str = tokens[2]
    if isinstance(num_str, str):
      # check if value referenced by variable is string
      if (num_str in self.variables):
        if isinstance(self.variables[num_str], str) and re.match(self.NUMBER_REGEX, self.variables[num_str]):
          self.variables["result"] = int(self.variables[num_str])
          self.ip_+=1
          return
        else:
          self.error(ErrorType.TYPE_ERROR, description=f"variable {num_str} references value {self.variables[num_str]} which does not convert to a valid integer", line_num=self.ip_)
      # check if formatted as valid number
      elif re.match(self.NUMBER_REGEX, num_str):
        self.variables["result"] = int(num_str)
      else:
        self.error(ErrorType.TYPE_ERROR, description=f"string to convert must be valid variable or represent valid integer", line_num=self.ip_)
    self.ip_+=1
  
  def process_input(self, tokens):
    # check if >= 3 arguments
    if (len(tokens) < 3):
      self.error(ErrorType.SYNTAX_ERROR, description=f"invalid number of arguments for funccall input, need at least 3, got {len(tokens)}", line_num=self.ip_)
    prompt_str = ""
    
    # concat all arguments
    for token in tokens[2:]:
      prompt_str += str(self.process_variable(token))
        
    self.output(prompt_str)
    self.variables["result"] = self.get_input()   
    self.ip_+=1
    
  def process_print(self, tokens):
    if (len(tokens) < 3):
      self.error(ErrorType.SYNTAX_ERROR, description=f"invalid number of arguments for funccall print, need at least 3, got {len(tokens)}", line_num=self.ip_)
    
    res_str = ""
    # concat all arguments
    for token in tokens[2:]:
      res_str += str(self.process_variable(token))
        
    self.output(res_str)
    self.ip_+=1
  
  def process_if(self, tokens):
    # check for expression after if
    if (len(tokens) < 2):
      self.error(ErrorType.SYNTAX_ERROR, description="if must be followed by expression", line_num=self.ip_)
      
    # check that indent is greater than outer block
    #if not self.block_stk or self.block_stk[-1][self.INDENT_IDX] >= self.indents[self.ip_]:
      #self.error(ErrorType.SYNTAX_ERROR, description="misaligned if statement")
    
    # process if expression
    expr_res = self.process_expression(tokens[1:])
    if (expr_res == True):
      # push if statement to indentations_stk since new block has been created
      self.block_stk.append([self.IF_DEF, self.indents[self.ip_], True])
      self.ip_+=1
    elif (expr_res == False):
      # push if statement to indentations_stk since new block has been created
      self.block_stk.append([self.IF_DEF, self.indents[self.ip_], False])
      # jump to next else or endif with same indentation
      for i in range(self.ip_+1, len(self.program)):
        if self.indents[i] == self.indents[self.ip_] and len(self.tokenized_lines[i]) >= 1 and (self.tokenized_lines[i][0] == self.ELSE_DEF or self.tokenized_lines[i][0] == self.ENDIF_DEF):
          self.ip_ = i
          return
    else:
      self.error(ErrorType.TYPE_ERROR, description=f"expression following if statement must evaluate to boolean", line_num=self.ip_)
      
  def process_else(self, tokens):  
    if (len(tokens) != 1):
      self.error(ErrorType.SYNTAX_ERROR, description=f"else may not be followed by an expression", line_num=self.ip_)
      
    if not self.block_stk:
      self.error(ErrorType.SYNTAX_ERROR, description="mismatched else statement", line_num=self.ip_)
      
    # already took if branch above
    if self.block_stk[-1][self.INFO_IDX]:
      # jump to next endif with same indentation
      for i in range(self.ip_+1, len(self.program)):
        if self.indents[i] == self.indents[self.ip_] and len(self.tokenized_lines[i]) >= 1 and self.tokenized_lines[i][0] == self.ENDIF_DEF:
          self.ip_ = i
          return
    else:
      self.ip_+=1
      
  def process_endif(self, tokens):
    if (len(tokens) != 1):
      self.error(ErrorType.SYNTAX_ERROR, description=f"endif may not be followed by an expression", line_num=self.ip_)
    
    # check that innermost open block is an if with same indent
    if not self.block_stk or self.block_stk[-1][self.TYPE_IDX] != self.IF_DEF or self.block_stk[-1][self.INDENT_IDX] != self.indents[self.ip_]:
      self.error(ErrorType.SYNTAX_ERROR, description="mismatched endif statement", line_num=self.ip_)
      
    self.block_stk.pop() # pop current block
    self.ip_+=1
       
  def process_while(self, tokens):
    # check for expression after while
    if (len(tokens) < 2):
      self.error(ErrorType.SYNTAX_ERROR, description="while must be followed by expression", line_num=self.ip_)
      
    # check that indent is greater than outer block
    #if not self.block_stk or (self.block_stk[-1][self.INFO_IDX][-1][self.INDENT_IDX] >= self.indents[self.ip_]) :
      #self.error(ErrorType.SYNTAX_ERROR, description="misaligned while statement")
    
    # when first encountering while, find corresponding endwhile and insert into block_stk
    if not self.block_stk or self.block_stk[-1][self.TYPE_IDX] != self.WHILE_DEF or self.block_stk[-1][self.INFO_IDX][self.WHILE_IP] != self.ip_:
      for i in range(self.ip_+1, len(self.program)):
        if self.indents[i] == self.indents[self.ip_] and len(self.tokenized_lines[i]) >= 1 and self.tokenized_lines[i][0] == self.ENDWHILE_DEF:
          # push while statement to indentations_stk since new block has been created, store both ip to 
          # while and ip to line after endwhile (since it is easier to directly jump there after the 
          # while expression returns false)
          self.block_stk.append([self.WHILE_DEF, self.indents[self.ip_], [self.ip_, i+1]])
        
    # process expression for while statement
    expr_res = self.process_expression(tokens[1:])
    if (expr_res == True):
      # enter into while loop if expression returns true
      self.ip_+=1
    elif (expr_res == False):
      # finished with while loop
      # jump to ip after endwhile if expression returns false
      self.ip_ = self.block_stk[-1][self.INFO_IDX][self.AFTER_ENDWHILE_IP]
      # pop current block
      self.block_stk.pop()
    else:
      self.error(ErrorType.TYPE_ERROR, description=f"expression following while statement must evaluate to boolean", line_num=self.ip_)
      
  def process_endwhile(self, tokens):
    #self.error(ErrorType.SYNTAX_ERROR, description=f"I will get TikTok job if I fix this")
    if (len (tokens) != 1):
      self.error(ErrorType.SYNTAX_ERROR, description=f"endwhile may not be followed by an expression", line_num=self.ip_)
    
    # check that innermost open block is a while with same indent
    if not self.block_stk or self.block_stk[-1][self.TYPE_IDX] != self.WHILE_DEF or self.block_stk[-1][self.INDENT_IDX] != self.indents[self.ip_]:
      self.error(ErrorType.SYNTAX_ERROR, description="mismatched endwhile statement", line_num=self.ip_)
    
    # move ip back to while condition
    self.ip_ = self.block_stk[-1][self.INFO_IDX][self.WHILE_IP]
      
  def process_assign(self, tokens):
    if (len(tokens) < 2):
      self.error(ErrorType.SYNTAX_ERROR, description=f"invalid number of arguments for assign, need 3, got {len(tokens)}", line_num=self.ip_)
    var_name = tokens[1]
    if (re.match(self.NAME_REGEX, var_name)) is None:
      self.error(ErrorType.SYNTAX_ERROR, description="variables names must begin with letters and consist of letters, numbers, and underscores", line_num=self.ip_)
    if (len(tokens) == 3):
      var_val = self.process_variable(tokens[2])
    else:
      var_val = self.process_expression(tokens[2:])
    
    self.variables[var_name] = var_val
    self.ip_+=1
    
  def process_variable(self, v):
    if (re.match(self.NUMBER_REGEX, v)):
      return int(v)
    # match variable in dictionary
    elif (v in self.variables):
      return self.variables[v]
    # strip quotes
    elif (re.match("\".*\"", v)):
      return v[1:-1]
    # return actual boolean
    elif (v == 'True'):
      return True
    elif (v == 'False'):
      return False
    else:
      self.error(ErrorType.NAME_ERROR, description=f"variable {v} is not defined", line_num=self.ip_)
    
  def process_expression(self, tokens):
    for token in tokens:
      if token in self.OPERATORS:
        self.operator_stk.append(token)
      else:
        self.operand_stk.append(self.process_variable(token))
        
    # for every operand, apply operator to top two operators on operator stack
    # and push result back onto stack
    while (self.operator_stk and len(self.operand_stk) >= 2):
      op = self.operator_stk.pop()
      b = self.operand_stk.pop()
      a = self.operand_stk.pop()
      res = self.compute(op, a, b)
      self.operand_stk.append(res)
    
    if (self.operator_stk or len(self.operand_stk) > 1):
      self.error(ErrorType.SYNTAX_ERROR, description="improper expression syntax", line_num=self.ip_)
    
    # if valid syntax, should only have 1 operand left at the end
    return self.operand_stk.pop()
    
  def compute(self, op, a, b):
    # check type mismatch
    if type(a) is not type(b):
      self.error(ErrorType.TYPE_ERROR, description=f"mismatched types '{type(a)}' and '{type(b)}'", line_num=self.ip_)
      
    # operators that apply for all types
    if op == '==':
      return a == b
    elif op == '!=':
      return a != b
    
    # operators that apply for int and str
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
      
    # operators that apply for int
    if isinstance(a, int) and not isinstance(a, bool):
      if op == '-':
        return a-b
      elif op == '*':
        return a*b
      elif op == '/':
        return a//b
      elif op == '%':
        return a % b
      
    # operators that apply for bool
    if isinstance(a, bool):
      if op == '&':
        return a and b
      elif op == '|':
        return a or b
  
    return self.error(ErrorType.TYPE_ERROR, description=f"operands of type '{type(a)}' incompatible with operator '{op}'", line_num=self.ip_)
      
      
      
#i.run(['func main', ' assign i 0', ' while < i 2', '  funccall print "Outer: " i', '  assign j 3', '  while > j 0','   funccall print "Inner: " j','   assign j - j 1', '  endwhile', '  funccall print "Outer end: " i', '  assign i + i 1', ' endwhile', 'endfunc'])

#i.run(['func main',' assign n 5',' assign f 1',' funccall fact',' funccall print result','endfunc','','func fact',' if == n 0','  return f',' endif',' assign f * f n',' assign n - n 1',' funccall fact','endfunc'])