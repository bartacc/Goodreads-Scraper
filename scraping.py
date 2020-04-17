import requests
from bs4 import BeautifulSoup
import sqlite3

DATABASE_NAME = 'quotesDB.db'


def load_quote_author_and_work(quoteTag):
    #Load the quoteText div and remove script tags from it (if any exist)
    block = quoteTag.find('div', class_='quoteText')

    while block.script is not None:
        block.script.decompose()

    #Find author name, then remove it from HTML document
    author = block.span.text
    author = str(author).strip().replace(',', '')

    block.span.decompose()

    #Find work name (if exists), then remove it from HTML document 
    work = block.span
    if work is not None:
        work = work.text.strip()
        block.span.decompose()

    #Extract quote's text
    del block['class']
    quoteText = str(block)
    quoteText = quoteText.replace('<div>', '').replace('</div>', '').replace('―', '').replace('“', '').replace('”', '')
    quoteText = replace_last_string(quoteText, '<br/>', '').strip()


    data = [quoteText, author]
    if work is not None:
        data.append(work)

    return data

def load_author_info(bioPage):
    #Find information about the author in HTML
    aboutAuthorTag = bioPage.find('div', class_ = 'aboutAuthorInfo')
    #If there is no link (no photo) to author's bio
    if aboutAuthorTag is None or aboutAuthorTag.span is None:
        return None

    info = aboutAuthorTag.span.next_sibling.next_sibling

    #If the author's bio is so short that there is no second span with longer text
    if info is None:
        info = bioPage.find('div', class_ = 'aboutAuthorInfo').span



    #Remove all link (<a>) tags pointing to a goodreads page
    linksInInfo = info.find_all('a')
    for link in linksInInfo:
        if 'goodreads' in link['href']:
            link.unwrap()
    
    #Remove attributes of span tag
    del info['id']
    del info['style']
    info.smooth()

    info = str(info)
    info = info.replace('<span>', '').replace('</span>', '')

    return info

def create_db():
    dbConnection = sqlite3.connect(DATABASE_NAME)
    dbCursor = dbConnection.cursor()
    dbCursor.execute('CREATE TABLE `Authors` ( `Name` TEXT NOT NULL UNIQUE, `Info` TEXT NOT NULL, `Image` BLOB NOT NULL, PRIMARY KEY(`Name`) )')
    dbCursor.execute('CREATE TABLE "Quotes" ( `Quote` TEXT NOT NULL UNIQUE, `Author` TEXT NOT NULL, `Cited_Work` TEXT, PRIMARY KEY(`Quote`), FOREIGN KEY(`Author`)REFERENCES `Authors`(`Name`) )')

    dbConnection.commit()
    dbConnection.close()

#Saves evrything from currentData to a SQLite database
#
#Scraped data in following format: 
#{'authorName': 
#   {'image': imgBytes,
#    'bio': bioText,
#    'quoteAuthorWork': [(quote, author, work), (quote, author, work)...]}
# }
def save_to_db(currentData):
    print('[+]Saving to Database')
    dbConnection = sqlite3.connect(DATABASE_NAME)
    dbCursor = dbConnection.cursor()

    for author in currentData:
        authorsData = currentData[author]

        #If this author is already in the database, don't insert it twice
        dbCursor.execute('SELECT * FROM Authors WHERE Name=?', (author, ))
        matchingAuthors = dbCursor.fetchall()
        if len(matchingAuthors) == 0:
            authorRowContent = (author, authorsData['bio'], authorsData['image'])
            dbCursor.execute('INSERT INTO Authors VALUES (?, ?, ?)', authorRowContent)

        for quoteAuthorWork in authorsData['quoteAuthorWork']:
            qouteRowContent = (quoteAuthorWork[0], quoteAuthorWork[1], None if len(quoteAuthorWork) < 3 else quoteAuthorWork[2])
            print(qouteRowContent)
            dbCursor.execute('INSERT INTO Quotes VALUES (?, ?, ?)', qouteRowContent)
        
        dbConnection.commit()
    dbConnection.close()
    print('[+]All saved')

def replace_last_string(string, find, replace):
    reversed = string[::-1]
    replaced = reversed.replace(find[::-1], replace[::-1], 1)
    return replaced[::-1]


def main():
    #create_db()

    for pageNumber in range(1, 100):
        currentData = {}

        r = requests.get(f'https://www.goodreads.com/quotes/tag/philosophy?page={pageNumber}')
        print(f'     [+]Loaded Page {pageNumber}, Status: {r.status_code}   Time: {r.elapsed}')
        page = r.text
        soup = BeautifulSoup(page, 'html.parser')

        quotes = soup.find_all('div', class_='quote')
        for quoteTag in quotes:
            #An array: [quote, authorName, citedWork]
            quoteAuthorWork = load_quote_author_and_work(quoteTag)
            print(f'[+]Loading quote by {quoteAuthorWork[1]}')

            #Load the Bio Page
            linkToBioPage = quoteTag.find('a')['href']
            if 'http' in linkToBioPage:
                print("[-]Link to bio page points to a site outside of goodreads, aborting")
                continue
            bioPageResponse = requests.get('https://www.goodreads.com' + linkToBioPage)
            bioPageRaw = bioPageResponse.text
            bioPage = BeautifulSoup(bioPageRaw, 'html.parser')
            print(f'[+]Bio page loaded, Status: {bioPageResponse.status_code}   Time: {bioPageResponse.elapsed}')

            authorInfo = load_author_info(bioPage)
            #Skip this quote if can't find info about the author
            if authorInfo is None:
                print("[-]Can't find info about the author, aborting")
                continue

            
            #Load the image page
            linkToImgPage = bioPage.find('div', class_ = 'authorLeftContainer').a['href']
            imgPageResponse = requests.get('https://www.goodreads.com' + linkToImgPage)
            imgPageRaw = imgPageResponse.text
            imgPage = BeautifulSoup(imgPageRaw, 'html.parser')
            print(f'[+]Image page loaded, Status: {imgPageResponse.status_code}   Time: {imgPageResponse.elapsed}')

            #Download the author's image
            imgLink = imgPage.find('div', class_ = 'left').div.a['href']
            image = requests.get(imgLink)
            print(f'[+]Image loaded, Status: {image.status_code}   Time: {image.elapsed}')
            

            #Save this quotes (and author) data to a global variable
            if quoteAuthorWork[1] not in currentData:
                currentData[quoteAuthorWork[1]] = {'image': image.content,
                                            'bio': authorInfo,
                                            'quoteAuthorWork': [(quoteAuthorWork[0], quoteAuthorWork[1], None if len(quoteAuthorWork) < 3 else quoteAuthorWork[2])]}
            else:
                currentData[quoteAuthorWork[1]]['quoteAuthorWork'].append((quoteAuthorWork[0], quoteAuthorWork[1], None if len(quoteAuthorWork) < 3 else quoteAuthorWork[2]))

            
        
        save_to_db(currentData)

        

if __name__ == '__main__':
    main()






