from fastapi import FastAPI,HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel
import logging
import os
import tempfile
import subprocess
import json

app = FastAPI()

logging.basicConfig(level=logging.INFO,)
logger=logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)


app.mount("/static", StaticFiles(directory="static"), name="static")

#loading the html file from static dir
@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html") as f:
        return f.read()


class RepoLink(BaseModel):
    repo_url: str
    

def llm_chain(python_code):
    try :
        code= python_code
    
        os.environ["OPENAI_API_KEY"]=''

        model = ChatOpenAI(model="gpt-4")
    
        user_template="""
You are an expert programmer with deep knowledge of Python code. Analyze the provided code to count the exact occurrences of if, for, and while constructs. 
Only count these keywords when they are used as actual constructs in the code, not when they appear inside strings or comments.

Instructions:

1. Analyse the code line by line.
2. Count the if, for, and while constructs.
3. Dont count 'if' construct twice when associated with the 'else' construct
4. Exclude any occurrences within strings or comments.
5. Identify and count nested constructs:
      a. if inside for (if_in_for)
      b. while inside if (while_in_if)
      c. for inside while (for_in_while)
      d. if inside while (if_in_while)
      e. for inside if (for_in_if)
      f. while inside for (while_in_for)

Return the results only in the following JSON format(dont include explanations):

  "if": <count>,
  "for": <count>,
  "while": <count>,
  "if_in_for": <count>,
  "for_in_if": <count>,
  "while_in_if": <count>,
  "if_in_while": <count>,
  "for_in_while": <count>,
  "while_in_for": <count>


Python code for which you need to count the contructs : {code}
 
your Answer:
"""
        parser=StrOutputParser()
    
        prompt=ChatPromptTemplate([('user',user_template)])

        chain = prompt | model | parser
    
        response=chain.invoke({'code':code})

        logger.info("Successfully retreived response from LLM")
        return response
    
    except Exception as e:
        logger.error(f"Error in retreiving response from Openai LLM{e}")
        raise
        

@app.post("/analyze-repo/")
async def analyze_repo(repo_link: RepoLink):
    logger.info("Entered FastAPI endpoint")
    
    python_files = []
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_name = os.path.basename(repo_link.repo_url)
            subprocess.run(["git", "clone", repo_link.repo_url, tmpdir], check=True)
            logger.info(f"Successfully cloned Git Repo {repo_name}")
    
            #Retrieving the Python files
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    if file.endswith(".py"):
                        file_path = os.path.join(root, file)
                        with open(file_path, "r") as f:
                            code = f.read()
                            python_files.append((file, code))
        
            if not python_files:
                logger.warning("No Python files found in the repository.")
                return {".py":"NOT FOUND"}
                
    except Exception as e:
        logger.error(f"Error in cloning the repo or retrieving Python files: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process the repository.")

    #code analysis with llm
    try:
        results = {}
        for filename, code in python_files:
            response = llm_chain(code)
            
            decoded_response = json.loads(response)
            
            results[filename] = decoded_response
            
        
        logger.info(f"Successfully analyzed all the Python files in the Git repo, result: {results}")
        
        return results

    except Exception as e:
        logger.error(f"Error in analyzing the Python files: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze the Python files.")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)





