import time
from typing import Optional

import yfinance as yf

import pixeltable as pxt
from pixeltable.functions.openai import chat_completions, invoke_tools

DIRECTORY = 'agent'
OPENAI_MODEL = 'gpt-4o-mini'

# Start timing
start_time = time.time()

# Create Fresh Directory
pxt.drop_dir(DIRECTORY, force=True)
pxt.create_dir(DIRECTORY, if_exists='ignore')


# yfinance tool
@pxt.udf
def stock_info(ticker: str) -> Optional[dict]:
    """Get stock info for a given ticker symbol."""
    stock = yf.Ticker(ticker)
    return stock.info


# Financial analyst tool
@pxt.udf
def financial_analyst_tool(query: str) -> Optional[dict]:
    """Ask your financial analyst any question."""
    finance_agent = pxt.get_table(f'{DIRECTORY}.financial_analyst')
    finance_agent.insert([{'prompt': query}])
    return finance_agent.select(finance_agent.answer).collect()[0]


# Create prompt with tool outputs
@pxt.udf
def create_prompt(question: str, tool_outputs: list[dict]) -> str:
    return f"""
    QUESTION:

    {question}

    RESULTS:

    {tool_outputs}
    """


######### 1. Create Finance Analyst Table #########
finance_agent = pxt.create_table(f'{DIRECTORY}.financial_analyst', {'prompt': pxt.String}, if_exists='ignore')
messages = [{'role': 'user', 'content': finance_agent.prompt}]

tools = pxt.tools(stock_info)

# Add initial response from OpenAI
finance_agent.add_computed_column(
    initial_response=chat_completions(
        model=OPENAI_MODEL, messages=messages, tools=tools, tool_choice=tools.choice(required=True)
    )
)

# Invoke tools
finance_agent.add_computed_column(tool_output=invoke_tools(tools, finance_agent.initial_response))

# Create prompt with invoked response
finance_agent.add_computed_column(stock_response_prompt=create_prompt(finance_agent.prompt, finance_agent.tool_output))

# Send back to OpenAI for final response
messages = [
    {'role': 'system', 'content': "Answer the user's question based on the results."},
    {'role': 'user', 'content': finance_agent.stock_response_prompt},
]
finance_agent.add_computed_column(final_response=chat_completions(model=OPENAI_MODEL, messages=messages))
finance_agent.add_computed_column(answer=finance_agent.final_response.choices[0].message.content)


######### 2. Create Portfolio Manager Table #########
portfolio_manager = pxt.create_table(f'{DIRECTORY}.portfolio_manager', {'prompt': pxt.String}, if_exists='ignore')
messages = [{'role': 'user', 'content': portfolio_manager.prompt}]

tools = pxt.tools(financial_analyst_tool)

# Add initial response from OpenAI
portfolio_manager.add_computed_column(
    initial_response=chat_completions(
        model=OPENAI_MODEL, messages=messages, tools=tools, tool_choice=tools.choice(required=True)
    )
)

# Invoke tools
portfolio_manager.add_computed_column(tool_output=invoke_tools(tools, portfolio_manager.initial_response))

# Create prompt with invoked response
portfolio_manager.add_computed_column(
    stock_response_prompt=create_prompt(portfolio_manager.prompt, portfolio_manager.tool_output)
)

# Send back to OpenAI for final response
messages = [
    {'role': 'system', 'content': "Answer the user's question based on the results."},
    {'role': 'user', 'content': portfolio_manager.stock_response_prompt},
]
portfolio_manager.add_computed_column(final_response=chat_completions(model=OPENAI_MODEL, messages=messages))
portfolio_manager.add_computed_column(answer=portfolio_manager.final_response.choices[0].message.content)


##### 3. Test agents #####
finance_agent = pxt.get_table(f'{DIRECTORY}.financial_analyst')
portfolio_manager = pxt.get_table(f'{DIRECTORY}.portfolio_manager')
portfolio_manager.insert([{'prompt': 'I need a financial report for NVDIA'}])


# End timing and print execution time
end_time = time.time()
execution_time = end_time - start_time
print(f'\nTotal execution time: {execution_time:.2f} seconds')
