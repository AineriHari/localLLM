"""
Module for retrieving documents based on user queries using FAISS.

This module provides functionality to retrieve relevant documents from a FAISS index
using embeddings generated from user queries. It handles document management by copying
retrieved documents to a designated folder for easy access.

Key Functions:
- retrieve_documents: Retrieves relevant documents for a given query using a FAISS index.
"""

import os
import numpy as np
from typing import Tuple
import google.generativeai as genai
from utils.model_loader import load_model


def analyze_chunk_with_llm(model: genai.GenerativeModel, chunk: bytes, query: str) -> Tuple[bool, bytes]:
    """
    Analyzes a text chunk to determine its relevance to a user query using a Generative AI model.

    Args:
        model (genai.GenerativeModel): An instance of the GenerativeModel used to generate responses.
        chunk (bytes): The text chunk that needs to be analyzed for relevance.
        query (str): The user question to which the relevance of the text chunk will be evaluated.

    Returns:
        Tuple[bool, bytes]: A tuple where the first element is a boolean indicating
                            whether the chunk is relevant to the query ('yes' or 'no'),
                            and the second element is the original text chunk.
    """
    # Define the prompt
    content = [f"system role: Given the user question: {query}, is the following text relevant and can be useful to "
               f"answer to the question?\n\n{chunk}\n\nAnswer 'yes' or 'no'."]

    # Generate response using the Gemini model
    response = model.generate_content(content)

    # return the boolean and chunk
    return response.text.strip().lower() == 'yes', chunk


def retrieve_documents(
        faiss_index,
        model,
        query,
        filenames_mapping,
        model_name: str = "gemini-1.5-flash",
        k=3
):
    """
    Retrieves relevant documents based on the user query using FAISS.

    Args:
        faiss_index: The FAISS index containing the indexed documents.
        model: The model (e.g., SentenceTransformer) used to encode the query.
        query (str): The user's query.
        filenames_mapping: A dictionary mapping FAISS indices to the actual document filenames.
        model_name (str, optional): The name of the generative AI model to load. Defaults to "gemini-1.5-flash".
        k (int): The number of documents to retrieve.

    Returns:
        list: A list of document filenames corresponding to the retrieved documents.
    """
    try:
        print(f"Retrieving documents for query: {query}")
        
        # Encode the query into embeddings
        query_embedding = model.encode([query], convert_to_tensor=False)
        query_embedding = np.array(query_embedding).astype('float32')

        # Search the FAISS index
        _, indices = faiss_index.search(query_embedding, k)
        
        files = []
        session_documents_folder = os.path.abspath(os.path.join('retrieved_documents'))
        os.makedirs(session_documents_folder, exist_ok=True)

        # Load the Gemini model
        model = load_model(model_name)

        # Iterate over the search results
        for idx in indices[0]:
            # Fetch the document filename from the filenames_mapping based on the FAISS index
            doc_filename = filenames_mapping.get(idx, None)
            
            if doc_filename:
                # Path to the uploaded document
                doc_path = os.path.abspath(os.path.join('uploaded_documents', doc_filename))
                
                if os.path.exists(doc_path):
                    # Copy or move the document to the static folder
                    dest_path = os.path.join(
                        session_documents_folder,
                        f"{idx}{os.path.splitext(doc_filename)[-1]}"
                    )

                    # remove the destination file is already present
                    if os.path.exists(dest_path):
                        os.remove(dest_path)

                    # Copy document to the static folder
                    with open(doc_path, 'rb') as f:
                        content = f.read()

                        # Analyze the document is related to query
                        is_relevant, useful_chunk = analyze_chunk_with_llm(
                            model=model,
                            chunk=content,
                            query=query
                        )
                        print(f"Is relevant status: {is_relevant} for document: {doc_path}")
                        if not is_relevant:
                            # if the is relevant is false which means the query is not related to that documents
                            # hence skipping
                            continue

                        with open(dest_path, 'wb') as f:
                            f.write(useful_chunk)
                        print(f"Saved document: {dest_path}")
                    
                    # Store the relative path from the static folder
                    relative_path = os.path.abspath(os.path.join(
                        'retrieved_documents', f"{idx}{os.path.splitext(doc_filename)[-1]}")
                    )
                    files.append(relative_path)
                    print(f"Added document to list: {relative_path}")
                else:
                    print(f"Document not found: {doc_path}")
            else:
                print(f"No filename found for index {idx}")
        
        print(f"Total {len(files)} documents retrieved. Paths: {files}")
        return files
    except Exception as e:
        print(f"Error retrieving documents: {e}")
        return []
