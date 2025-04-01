import json
import yaml
import logging
import argparse
from openai import OpenAI
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("seer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_prompts(file_path: str = 'prompts.yaml') -> Dict[str, str]:
    """Load prompts from a YAML file."""
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except (yaml.YAMLError, FileNotFoundError) as e:
        logger.error(f"Failed to load prompts from {file_path}: {e}")
        raise

def get_movie_info(movie_name: str, client: OpenAI, model: str) -> Dict[str, Any]:
    """Get movie information using the LLM."""
    try:
        prompts = load_prompts()
        
        movie_year_retrieval_prompt = prompts['retrieve_movie_year'].format(movie=f"\"{movie_name}\"")
        
        logger.info(f"Requesting information for movie: {movie_name}")
        
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that always outputs in valid JSON format. The only valid keys for the JSON output are 'title' and 'year'."},
                {"role": "user", "content": movie_year_retrieval_prompt},
            ],
            temperature=0.05,
            max_tokens=1000,
            n=1
        )
        
        json_content = completion.choices[0].message.content
        logger.debug(f"Raw response: {json_content}")
        
        return parse_and_validate_json(json_content, client, model)
        
    except Exception as e:
        logger.error(f"Error in get_movie_info: {e}", exc_info=True)
        return {"title": "Unknown", "year": 0, "error": str(e)}

def parse_and_validate_json(json_content: str, client: OpenAI, model: str) -> Dict[str, Any]:
    """Parse and validate JSON content, attempt to fix if invalid."""
    try:
        movie_data = json.loads(json_content)
        
        # Check if the dictionary has the required keys
        if not all(key in movie_data for key in ['title', 'year']):
            logger.warning(f"JSON missing required keys: {movie_data}")
            raise ValueError("JSON is missing required keys 'title' and/or 'year'")
        
        logger.info("Successfully parsed valid JSON response")
        return movie_data
    
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Error with original response: {e}")
        logger.info("Attempting to fix the response format...")
        
        return attempt_json_fix(json_content, client, model)

def attempt_json_fix(json_content: str, client: OpenAI, model: str) -> Dict[str, Any]:
    """Attempt to fix invalid JSON by sending a new request to the LLM."""
    try:
        fix_prompt = f"""
        The following is an AI response that should be in JSON format with 'title' and 'year' keys, but it's not correctly formatted:
        
        {json_content}
        
        Please convert this to a valid JSON with only 'title' and 'year' keys.
        """
        
        logger.info("Sending fix request to model")
        fix_completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that always outputs in valid JSON format. The only valid keys for the JSON output are 'title' and 'year'."},
                {"role": "user", "content": fix_prompt},
            ],
            temperature=0.05,
        )
        
        fixed_json_content = fix_completion.choices[0].message.content
        logger.debug(f"Fixed response: {fixed_json_content}")
        
        movie_data = json.loads(fixed_json_content)
        
        # Check if the fixed dictionary has the required keys
        if not all(key in movie_data for key in ['title', 'year']):
            logger.error("Even after fixing, JSON is missing required keys")
            logger.debug(f"Raw fixed content: {fixed_json_content}")
            return {"title": "Unknown", "year": 0, "error": "Missing required keys after fix attempt"}
        
        logger.info("Successfully fixed the JSON format")
        return movie_data
            
    except Exception as e:
        logger.error(f"Error in fix attempt: {e}", exc_info=True)
        return {"title": "Unknown", "year": 0, "error": str(e)}

def setup_client(base_url: str = "http://localhost:8000/v1", api_key: str = "lm-studio") -> OpenAI:
    """Set up and return an OpenAI client."""
    return OpenAI(base_url=base_url, api_key=api_key)

def main():
    """Main function to run the movie info retrieval."""
    try:
        # Set up argument parser
        parser = argparse.ArgumentParser(description='Get movie information using an LLM.')
        parser.add_argument('movie_title', nargs='?', default="Batman Begins", 
                            help='Title of the movie to look up (default: Batman Begins)')
        parser.add_argument('--model', default="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
                            help='Model to use for inference')
        parser.add_argument('--base-url', default="http://localhost:8000/v1",
                            help='Base URL for the OpenAI API')
        parser.add_argument('--api-key', default="lm-studio",
                            help='API key for the OpenAI API')
        parser.add_argument('--debug', action='store_true',
                            help='Enable debug logging')
        
        args = parser.parse_args()
        
        # Set debug level if requested
        if args.debug:
            logger.setLevel(logging.DEBUG)
            for handler in logger.handlers:
                handler.setLevel(logging.DEBUG)
        
        logger.info(f"Starting movie info retrieval for: {args.movie_title}")
        
        # Initialize OpenAI client
        client = setup_client(args.base_url, args.api_key)
        
        # Get movie info
        movie_data = get_movie_info(args.movie_title, client, args.model)
        
        # Display results
        logger.info(f"Parsed dictionary: {movie_data}")
        print(f"Movie title: {movie_data['title']}")
        print(f"Release year: {movie_data['year']}")
        
        if 'error' in movie_data:
            logger.warning(f"Process completed with errors: {movie_data['error']}")
        
        return movie_data
        
    except Exception as e:
        logger.critical(f"Critical error in main function: {e}", exc_info=True)
        print("An error occurred. Check the logs for details.")
        return {"title": "Unknown", "year": 0, "error": str(e)}

if __name__ == "__main__":
    main()